import re
from datetime import date
from typing import Any, Dict, List, Optional, Tuple
from app.planner.plan_schema import Plan, AdHocMetric
from app.semantic.model import Metric, SemanticLayer
from app.semantic.join_graph import JoinGraph

# A metric that is one aggregate over one column: SUM("t"."c"), AVG("t"."c")...
_COLUMN_AGGREGATE = re.compile(r'^(?:SUM|AVG|MIN|MAX)\(\s*"([^"]+)"\s*\.\s*"([^"]+)"\s*\)$', re.IGNORECASE)


def record_sort_column(plan: Plan, semantic: SemanticLayer, fact_table: str) -> Optional[Tuple[str, str]]:
    """
    The (table, column) a record-level plan is ordered by, or None when it cannot be.

    "Top 10 records by delay_minutes" is a `detail` plan whose metric is delay_minutes:
    the metric names the column to rank, and this recovers that column from the
    metric's definition. Only a metric that is a plain aggregate of a column on the
    fact table qualifies - the ratio of two aggregates (average order value) has no
    per-record value to order by.
    """
    table_column: Optional[Tuple[str, str]] = None

    if isinstance(plan.metric, AdHocMetric):
        if "." in plan.metric.column:
            table_column = tuple(plan.metric.column.split(".", 1))  # type: ignore[assignment]
    elif isinstance(plan.metric, str):
        metric = next((m for m in semantic.metrics if m.name == plan.metric), None)
        match = _COLUMN_AGGREGATE.match(metric.expr.strip()) if metric else None
        if match:
            table_column = (match.group(1), match.group(2))

    if not table_column:
        return None
    table, column = table_column
    if table != fact_table or table not in semantic.tables or column not in semantic.tables[table].columns:
        return None
    return table, column


def period_expr(metric_obj: Optional[Metric], metric_expr: str, cond_sql: str) -> str:
    """
    Restricts a metric to one time window.

    DuckDB accepts FILTER only directly after a single aggregate call, so appending
    it to a compound expression (`SUM(a) / COUNT(b)`) is a syntax error. Metrics that
    need it therefore carry an `expr_conditional` template that places the predicate
    inside each aggregate; everything else takes the plain FILTER suffix.
    """
    if metric_obj is not None and metric_obj.expr_conditional:
        return metric_obj.expr_conditional.replace("{cond}", cond_sql)
    return f"{metric_expr} FILTER (WHERE {cond_sql})"

def compile_plan_to_sql(
    plan: Plan,
    semantic: SemanticLayer,
    target_window: Tuple[date, date],
    baseline_window: Optional[Tuple[date, date]] = None
) -> Tuple[str, Tuple[Any, ...]]:
    """
    Compiles a validated Plan into parameterized SQL and parameters tuple for DuckDB.
    """
    params: List[Any] = []

    # 1. Identify fact table and metric
    metric_name = plan.metric if isinstance(plan.metric, str) else None
    metric_obj: Optional[Metric] = None
    for m in semantic.metrics:
        if m.name == metric_name:
            metric_obj = m
            break

    fact_table = metric_obj.table if metric_obj else semantic.fact_table
    if fact_table not in semantic.tables:
        fact_table = semantic.fact_table
    if not fact_table:
        raise ValueError("This dataset has no tables to query.")

    # Primary time column
    time_col = None
    if plan.time and plan.time.column:
        time_col = plan.time.column
    elif metric_obj and metric_obj.time_column:
        time_col = metric_obj.time_column
    elif semantic.time.primary_column:
        time_col = semantic.time.primary_column
    else:
        # Never invent a column: guessing `order_date` is what made every non-retail
        # dataset fail with a missing-table or missing-column error.
        raise ValueError("This dataset has no date column, so a time window cannot be applied.")

    t_tbl, t_col = time_col.split(".", 1)

    # 2. Collect referenced tables and generate JOINs
    ref_tables = set()
    for dim in plan.dimensions:
        ref_tables.add(dim.split(".", 1)[0])
    for f in plan.filters:
        ref_tables.add(f.column.split(".", 1)[0])
    ref_tables.discard(fact_table)

    jg = JoinGraph(semantic.tables, semantic.relationships)
    joins_sql = []
    joined_tables = set()

    for target_tbl in sorted(ref_tables):
        path = jg.find_join_path(fact_table, target_tbl)
        if path:
            for c_tbl, c_col, p_tbl, p_col in path:
                if p_tbl not in joined_tables:
                    # Deduplicated CTE join for parent safety
                    joins_sql.append(
                        f'LEFT JOIN (SELECT * FROM "{p_tbl}" QUALIFY ROW_NUMBER() OVER (PARTITION BY "{p_col}" ORDER BY rowid) = 1) AS "{p_tbl}" '
                        f'ON "{c_tbl}"."{c_col}" = "{p_tbl}"."{p_col}"'
                    )
                    joined_tables.add(p_tbl)

    # Handle extra_joins on metric (e.g. return_rate)
    if metric_obj and metric_obj.extra_joins:
        for ej in metric_obj.extra_joins:
            ej_tbl = ej["table"]
            ej_alias = ej.get("alias", ej_tbl)
            if ej["mode"] == "distinct_semijoin":
                joins_sql.append(
                    f'LEFT JOIN (SELECT DISTINCT "order_id" FROM "{ej_tbl}") AS "{ej_alias}" ON {ej["on"]}'
                )

    joins_clause = "\n".join(joins_sql)

    # 3. Build Filters Clause
    where_parts = []
    for f in plan.filters:
        f_tbl, f_col = f.column.split(".", 1)
        val = f.value
        op = f.op

        if val == "(missing)" or val is None:
            if op in ["=", "in"]:
                where_parts.append(f'"{f_tbl}"."{f_col}" IS NULL')
            else:
                where_parts.append(f'"{f_tbl}"."{f_col}" IS NOT NULL')
        elif op == "in" and isinstance(val, list):
            placeholders = ", ".join(["?"] * len(val))
            where_parts.append(f'"{f_tbl}"."{f_col}" IN ({placeholders})')
            params.extend(val)
        elif op == "contains":
            where_parts.append(f'"{f_tbl}"."{f_col}" ILIKE \'%\' || ? || \'%\'')
            params.append(str(val))
        else:
            where_parts.append(f'"{f_tbl}"."{f_col}" {op} ?')
            params.append(val)

    # 4. Metric SQL Expression
    if metric_obj:
        metric_expr = metric_obj.expr
    elif isinstance(plan.metric, AdHocMetric):
        agg_fn = plan.metric.agg.upper()
        if agg_fn == "COUNT_DISTINCT":
            agg_fn = "COUNT(DISTINCT"
            m_tbl, m_col = plan.metric.column.split(".", 1)
            metric_expr = f'{agg_fn} "{m_tbl}"."{m_col}")'
        else:
            m_tbl, m_col = plan.metric.column.split(".", 1)
            metric_expr = f'{agg_fn}("{m_tbl}"."{m_col}")'
    else:
        # No metric resolved (only reachable for intents that do not aggregate one).
        # A row count is valid on any table, unlike a column named `amount`.
        metric_expr = "COUNT(*)"

    metric_alias = metric_name or "metric_val"

    # 5. Compile by Intent

    # --- KPI / COMPARISON KPI ---
    if plan.intent == "kpi":
        if plan.comparison and baseline_window:
            # Single scan conditional aggregation
            t_start, t_end = target_window
            b_start, b_end = baseline_window
            min_start = min(t_start, b_start)
            max_end = max(t_end, b_end)

            time_cond = f'"{t_tbl}"."{t_col}" >= ? AND "{t_tbl}"."{t_col}" < ?'
            all_where = [time_cond] + where_parts
            where_clause = "WHERE " + " AND ".join(all_where)

            # Insert overall window bound
            all_params = [min_start, max_end] + params

            # Use DuckDB native FILTER (WHERE ...) syntax
            cur_cond = f"\"{t_tbl}\".\"{t_col}\" >= '{t_start}' AND \"{t_tbl}\".\"{t_col}\" < '{t_end}'"
            prev_cond = f"\"{t_tbl}\".\"{t_col}\" >= '{b_start}' AND \"{t_tbl}\".\"{t_col}\" < '{b_end}'"
            cur_agg = period_expr(metric_obj, metric_expr, cur_cond)
            prev_agg = period_expr(metric_obj, metric_expr, prev_cond)

            sql = f'''
            SELECT 
                COALESCE({cur_agg}, 0) AS "current",
                COALESCE({prev_agg}, 0) AS "previous",
                (COALESCE({cur_agg}, 0) - COALESCE({prev_agg}, 0)) AS "delta",
                CASE WHEN COALESCE({prev_agg}, 0) = 0 THEN NULL
                     ELSE ROUND((COALESCE({cur_agg}, 0) - COALESCE({prev_agg}, 0)) * 100.0 / ABS({prev_agg}), 2)
                END AS "delta_pct"
            FROM "{fact_table}"
            {joins_clause}
            {where_clause}
            '''
            return sql.strip(), tuple(all_params)
        else:
            t_start, t_end = target_window
            where_parts.append(f'"{t_tbl}"."{t_col}" >= ? AND "{t_tbl}"."{t_col}" < ?')
            params.extend([t_start, t_end])
            where_clause = "WHERE " + " AND ".join(where_parts)

            sql = f'''
            SELECT {metric_expr} AS "{metric_alias}"
            FROM "{fact_table}"
            {joins_clause}
            {where_clause}
            '''
            return sql.strip(), tuple(params)

    # --- TREND ---
    elif plan.intent == "trend":
        grain = (plan.time.grain if plan.time and plan.time.grain else "month").lower()
        t_start, t_end = target_window
        where_parts.append(f'"{t_tbl}"."{t_col}" >= ? AND "{t_tbl}"."{t_col}" < ?')
        params.extend([t_start, t_end])
        where_clause = "WHERE " + " AND ".join(where_parts)

        # Snapshot metric handling (e.g. inventory)
        from_table_clause = f'"{fact_table}"'
        if metric_obj and metric_obj.time_behavior == "snapshot":
            from_table_clause = f'''
            (
                SELECT * FROM "{fact_table}"
                WHERE "{t_col}" >= '{t_start}' AND "{t_col}" < '{t_end}'
                QUALIFY "{t_col}" = MAX("{t_col}") OVER (PARTITION BY date_trunc('{grain}', "{t_col}"))
            ) AS "{fact_table}"
            '''

        if len(plan.dimensions) == 1:
            d_tbl, d_col = plan.dimensions[0].split(".", 1)
            dim_expr = f'COALESCE(CAST("{d_tbl}"."{d_col}" AS VARCHAR), \'(missing)\')'
            sql = f'''
            SELECT 
                date_trunc('{grain}', "{t_tbl}"."{t_col}")::DATE AS "period",
                {dim_expr} AS "{d_col}",
                {metric_expr} AS "{metric_alias}"
            FROM {from_table_clause}
            {joins_clause}
            {where_clause}
            GROUP BY 1, 2
            ORDER BY 1 ASC, "{metric_alias}" DESC
            '''
        else:
            sql = f'''
            SELECT 
                date_trunc('{grain}', "{t_tbl}"."{t_col}")::DATE AS "period",
                {metric_expr} AS "{metric_alias}"
            FROM {from_table_clause}
            {joins_clause}
            {where_clause}
            GROUP BY 1
            ORDER BY 1 ASC
            '''
        return sql.strip(), tuple(params)

    # --- BREAKDOWN / RANKING / COMPARE ---
    elif plan.intent in ["breakdown", "ranking", "compare"]:
        dim_selects = []
        dim_groups = []
        for i, dim in enumerate(plan.dimensions, 1):
            d_tbl, d_col = dim.split(".", 1)
            dim_expr = f'COALESCE(CAST("{d_tbl}"."{d_col}" AS VARCHAR), \'(missing)\')'
            dim_selects.append(f'{dim_expr} AS "{d_col}"')
            dim_groups.append(str(i))

        dim_select_str = ", ".join(dim_selects) if dim_selects else "'All' AS \"segment\""
        dim_group_str = ", ".join(dim_groups) if dim_groups else "1"

        if (plan.intent == "compare" or plan.comparison) and baseline_window:
            t_start, t_end = target_window
            b_start, b_end = baseline_window
            min_start = min(t_start, b_start)
            max_end = max(t_end, b_end)

            all_where = [f'"{t_tbl}"."{t_col}" >= ? AND "{t_tbl}"."{t_col}" < ?'] + where_parts
            all_params = [min_start, max_end] + params

            cur_cond = f"\"{t_tbl}\".\"{t_col}\" >= '{t_start}' AND \"{t_tbl}\".\"{t_col}\" < '{t_end}'"
            prev_cond = f"\"{t_tbl}\".\"{t_col}\" >= '{b_start}' AND \"{t_tbl}\".\"{t_col}\" < '{b_end}'"
            cur_agg = period_expr(metric_obj, metric_expr, cur_cond)
            prev_agg = period_expr(metric_obj, metric_expr, prev_cond)

            sort_col = '"delta" ASC' if (plan.sort and plan.sort.by == "delta" and plan.sort.dir == "asc") else '"delta" DESC'
            if plan.sort and plan.sort.by == "metric":
                sort_col = f'"current" {plan.sort.dir.upper()}'

            limit_str = f"LIMIT {plan.limit}" if plan.limit else ""

            sql = f'''
            SELECT 
                {dim_select_str},
                COALESCE({cur_agg}, 0) AS "current",
                COALESCE({prev_agg}, 0) AS "previous",
                (COALESCE({cur_agg}, 0) - COALESCE({prev_agg}, 0)) AS "delta",
                CASE WHEN COALESCE({prev_agg}, 0) = 0 THEN NULL
                     ELSE ROUND((COALESCE({cur_agg}, 0) - COALESCE({prev_agg}, 0)) * 100.0 / ABS({prev_agg}), 2)
                END AS "delta_pct"
            FROM "{fact_table}"
            {joins_clause}
            WHERE {' AND '.join(all_where)}
            GROUP BY {dim_group_str}
            ORDER BY {sort_col}
            {limit_str}
            '''
            return sql.strip(), tuple(all_params)
        else:
            t_start, t_end = target_window
            where_parts.append(f'"{t_tbl}"."{t_col}" >= ? AND "{t_tbl}"."{t_col}" < ?')
            params.extend([t_start, t_end])
            where_clause = "WHERE " + " AND ".join(where_parts)

            sort_dir = plan.sort.dir.upper() if plan.sort else "DESC"
            sort_by = f'"{metric_alias}" {sort_dir}'
            limit_str = f"LIMIT {plan.limit}" if plan.limit else ""

            sql = f'''
            SELECT 
                {dim_select_str},
                {metric_expr} AS "{metric_alias}"
            FROM "{fact_table}"
            {joins_clause}
            {where_clause}
            GROUP BY {dim_group_str}
            ORDER BY {sort_by}
            {limit_str}
            '''
            return sql.strip(), tuple(params)

    # --- DETAIL / FALLBACK ---
    else:
        t_start, t_end = target_window
        where_parts.append(f'"{t_tbl}"."{t_col}" >= ? AND "{t_tbl}"."{t_col}" < ?')
        params.extend([t_start, t_end])
        where_clause = "WHERE " + " AND ".join(where_parts)
        limit_val = plan.limit or 100

        cols_select = []
        if plan.dimensions:
            for dim in plan.dimensions:
                d_tbl, d_col = dim.split(".", 1)
                cols_select.append(f'"{d_tbl}"."{d_col}"')
        else:
            cols_select.append(f'"{fact_table}".*')

        # "Top / bottom N records by <column>": order by the metric's column, and lead
        # with it so the ranked value is the first thing in every row. A plan with no
        # sort, or a metric that is not one column, keeps the original unordered listing.
        order_clause = ""
        sort_column = (
            record_sort_column(plan, semantic, fact_table)
            if plan.sort and plan.sort.by == "metric" else None
        )
        if sort_column:
            ref = f'"{sort_column[0]}"."{sort_column[1]}"'
            if plan.dimensions:
                cols_select = [ref] + [c for c in cols_select if c != ref]
            direction = "ASC" if plan.sort.dir == "asc" else "DESC"
            # rowid breaks ties, so the same question always returns the same rows.
            order_clause = f'ORDER BY {ref} {direction} NULLS LAST, "{fact_table}".rowid'

        sql = f'''
        SELECT {", ".join(cols_select)}
        FROM "{fact_table}"
        {joins_clause}
        {where_clause}
        {order_clause}
        LIMIT {limit_val}
        '''
        return sql.strip(), tuple(params)
