from datetime import date
from typing import Any, Dict, List, Optional, Tuple
from app.planner.plan_schema import Plan, AdHocMetric
from app.semantic.model import Metric, SemanticLayer
from app.semantic.join_graph import JoinGraph

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

    fact_table = metric_obj.table if metric_obj else "sales"
    if fact_table not in semantic.tables:
        fact_table = "sales"

    # Primary time column
    time_col = None
    if plan.time and plan.time.column:
        time_col = plan.time.column
    elif metric_obj and metric_obj.time_column:
        time_col = metric_obj.time_column
    elif semantic.time.primary_column:
        time_col = semantic.time.primary_column
    else:
        time_col = f"{fact_table}.order_date"

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
        metric_expr = f'SUM("{fact_table}"."amount")'

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
            cur_agg = f"{metric_expr} FILTER (WHERE \"{t_tbl}\".\"{t_col}\" >= '{t_start}' AND \"{t_tbl}\".\"{t_col}\" < '{t_end}')"
            prev_agg = f"{metric_expr} FILTER (WHERE \"{t_tbl}\".\"{t_col}\" >= '{b_start}' AND \"{t_tbl}\".\"{t_col}\" < '{b_end}')"

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

            cur_agg = f"{metric_expr} FILTER (WHERE \"{t_tbl}\".\"{t_col}\" >= '{t_start}' AND \"{t_tbl}\".\"{t_col}\" < '{t_end}')"
            prev_agg = f"{metric_expr} FILTER (WHERE \"{t_tbl}\".\"{t_col}\" >= '{b_start}' AND \"{t_tbl}\".\"{t_col}\" < '{b_end}')"

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

        sql = f'''
        SELECT {", ".join(cols_select)}
        FROM "{fact_table}"
        {joins_clause}
        {where_clause}
        LIMIT {limit_val}
        '''
        return sql.strip(), tuple(params)
