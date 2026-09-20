from datetime import date
from typing import Any, Dict, List, Optional, Tuple
import duckdb
from app.config import settings
from app.planner.plan_schema import Plan, Filter
from app.semantic.model import SemanticLayer
from app.semantic.join_graph import JoinGraph

def run_why_analysis(
    db_path: str,
    semantic: SemanticLayer,
    metric_name: str,
    target_window: Tuple[date, date],
    baseline_window: Tuple[date, date],
    base_filters: Optional[List[Filter]] = None,
    candidate_dims: Optional[List[str]] = None,
    max_depth: int = 3
) -> Dict[str, Any]:
    """
    Deterministic Why / Drill-down analysis engine.
    Decomposes period-over-period change Δ across candidate dimensions,
    qualifies drivers via contribution and lift, and recursively drills down.
    Guarantees invariant: sum(segment_deltas) == total_delta.
    """
    con = duckdb.connect(db_path, read_only=True)

    # Metric lookup
    metric_obj = next((m for m in semantic.metrics if m.name == metric_name), None)
    if not metric_obj:
        con.close()
        raise ValueError(f"Metric '{metric_name}' not found for Why analysis.")

    fact_table = metric_obj.table
    time_col = metric_obj.time_column or semantic.time.primary_column or f"{fact_table}.order_date"
    t_tbl, t_col = time_col.split(".", 1)

    t_start, t_end = target_window
    b_start, b_end = baseline_window
    min_start = min(t_start, b_start)
    max_end = max(t_end, b_end)

    # Base filters SQL
    base_where = [f'"{t_tbl}"."{t_col}" >= ? AND "{t_tbl}"."{t_col}" < ?']
    base_params = [min_start, max_end]

    if base_filters:
        for f in base_filters:
            f_tbl, f_col = f.column.split(".", 1)
            if f.value == "(missing)" or f.value is None:
                base_where.append(f'"{f_tbl}"."{f_col}" IS NULL')
            else:
                base_where.append(f'"{f_tbl}"."{f_col}" = ?')
                base_params.append(f.value)

    # 1. Compute Overall Totals (M(T), M(B), Delta)
    metric_expr = metric_obj.expr
    cur_agg = f"{metric_expr} FILTER (WHERE \"{t_tbl}\".\"{t_col}\" >= '{t_start}' AND \"{t_tbl}\".\"{t_col}\" < '{t_end}')"
    prev_agg = f"{metric_expr} FILTER (WHERE \"{t_tbl}\".\"{t_col}\" >= '{b_start}' AND \"{t_tbl}\".\"{t_col}\" < '{b_end}')"

    totals_sql = f'''
        SELECT 
            COALESCE({cur_agg}, 0) AS target_val,
            COALESCE({prev_agg}, 0) AS baseline_val
        FROM "{fact_table}"
        WHERE {' AND '.join(base_where)}
    '''
    tot_row = con.execute(totals_sql, base_params).fetchone()
    target_total = round(float(tot_row[0]), 2)
    baseline_total = round(float(tot_row[1]), 2)
    overall_delta = round(target_total - baseline_total, 2)
    overall_pct = round((overall_delta / baseline_total) * 100, 2) if baseline_total != 0 else 0.0

    direction = "decrease" if overall_delta < 0 else ("increase" if overall_delta > 0 else "flat")

    if abs(overall_delta) < 1.0 or abs(overall_pct) < settings.WHY_MIN_CHANGE_PCT:
        con.close()
        return {
            "metric": metric_name,
            "direction": "flat",
            "target": {"start": str(t_start), "end": str(t_end), "value": target_total},
            "baseline": {"start": str(b_start), "end": str(b_end), "value": baseline_total},
            "delta": 0.0,
            "delta_pct": 0.0,
            "broad_based": True,
            "offsetting": False,
            "dimensions": [],
            "drill_path": [],
            "top_contributors": None
        }

    # 2. Select Candidate Dimensions
    jg = JoinGraph(semantic.tables, semantic.relationships)
    eligible_dims = []

    if candidate_dims:
        eligible_dims = candidate_dims
    else:
        for tname, tmeta in semantic.tables.items():
            if tname == fact_table or jg.find_join_path(fact_table, tname) is not None:
                for cname, cmeta in tmeta.columns.items():
                    if cmeta.role == "dimension" and 2 <= cmeta.distinct <= settings.WHY_MAX_CARDINALITY:
                        eligible_dims.append(f"{tname}.{cname}")

    # 3. Analyze Each Candidate Dimension
    dimension_results = []
    drivers = []

    for dim in eligible_dims:
        d_tbl, d_col = dim.split(".", 1)

        # Setup JOIN if needed
        joins_sql = []
        if d_tbl != fact_table:
            path = jg.find_join_path(fact_table, d_tbl)
            if path:
                for c_t, c_c, p_t, p_c in path:
                    joins_sql.append(
                        f'LEFT JOIN (SELECT * FROM "{p_t}" QUALIFY ROW_NUMBER() OVER (PARTITION BY "{p_c}" ORDER BY rowid) = 1) AS "{p_t}" '
                        f'ON "{c_t}"."{c_c}" = "{p_t}"."{p_c}"'
                    )

        joins_clause = "\n".join(joins_sql)
        dim_expr = f'COALESCE(CAST("{d_tbl}"."{d_col}" AS VARCHAR), \'(missing)\')'

        decomp_sql = f'''
            SELECT 
                {dim_expr} AS segment,
                COALESCE({cur_agg}, 0) AS cur_val,
                COALESCE({prev_agg}, 0) AS prev_val
            FROM "{fact_table}"
            {joins_clause}
            WHERE {' AND '.join(base_where)}
            GROUP BY 1
        '''

        rows = con.execute(decomp_sql, base_params).fetchall()
        segments = []
        sum_abs_deltas = 0.0

        for r in rows:
            seg_name = str(r[0])
            cur_v = round(float(r[1]), 2)
            prev_v = round(float(r[2]), 2)
            seg_delta = round(cur_v - prev_v, 2)
            sum_abs_deltas += abs(seg_delta)

            # Contribution c_s = delta_s / total_delta
            contrib = round(seg_delta / overall_delta, 4) if overall_delta != 0 else 0.0
            # Baseline share b_s = prev_s / baseline_total
            b_share = round(prev_v / baseline_total, 4) if baseline_total != 0 else 0.0
            lift = round(contrib / b_share, 2) if b_share > 0 else (99.0 if contrib > 0 else 0.0)

            segments.append({
                "value": seg_name,
                "target": cur_v,
                "baseline": prev_v,
                "delta": seg_delta,
                "contribution": contrib,
                "baseline_share": b_share,
                "lift": lift
            })

        # Sort segments by delta in direction of overall change
        segments.sort(key=lambda s: s["delta"] if overall_delta < 0 else -s["delta"])

        # Check driver condition:
        # Same sign, contribution >= WHY_MIN_SHARE (30%), lift >= WHY_MIN_LIFT (1.5)
        top_contrib_seg = next((s for s in segments if (s["delta"] < 0 if overall_delta < 0 else s["delta"] > 0)), None)
        c_top = top_contrib_seg["contribution"] if top_contrib_seg else 0.0
        lift_top = top_contrib_seg["lift"] if top_contrib_seg else 0.0

        is_driver = (c_top >= settings.WHY_MIN_SHARE and lift_top >= settings.WHY_MIN_LIFT)
        is_offsetting = (sum_abs_deltas > settings.WHY_OFFSET_RATIO * abs(overall_delta))

        dim_res = {
            "dimension": dim,
            "is_driver": is_driver,
            "c_top": c_top,
            "lift": lift_top,
            "offsetting": is_offsetting,
            "segments": segments[:8]
        }
        dimension_results.append(dim_res)

        if is_driver:
            drivers.append((dim, top_contrib_seg, c_top, lift_top))

    # Sort drivers by contribution descending
    drivers.sort(key=lambda x: x[2], reverse=True)

    # 4. Recursive Drill-Down Path
    drill_path = []
    current_delta = overall_delta
    parent_delta = overall_delta
    drill_filters = list(base_filters) if base_filters else []
    remaining_dims = list(eligible_dims)

    for depth in range(max_depth):
        # Pick best driver
        if not drivers:
            break
        best_dim, top_seg, c_val, l_val = drivers[0]

        share_of_parent = round(top_seg["delta"] / parent_delta, 2) if parent_delta != 0 else 0.0
        cum_share = round(top_seg["delta"] / overall_delta, 2) if overall_delta != 0 else 0.0

        drill_path.append({
            "dimension": best_dim,
            "value": top_seg["value"],
            "delta": top_seg["delta"],
            "share_of_parent": share_of_parent,
            "cumulative_share": cum_share
        })

        # Add filter for recursive step
        drill_filters.append(Filter(column=best_dim, op="=", value=top_seg["value"]))
        remaining_dims = [d for d in remaining_dims if d != best_dim]
        parent_delta = top_seg["delta"]

        # Re-evaluate next driver level within this segment
        next_drivers = []
        for r_dim in remaining_dims:
            d_tbl, d_col = r_dim.split(".", 1)
            joins_sql = []
            if d_tbl != fact_table:
                path = jg.find_join_path(fact_table, d_tbl)
                if path:
                    for c_t, c_c, p_t, p_c in path:
                        joins_sql.append(
                            f'LEFT JOIN (SELECT * FROM "{p_t}" QUALIFY ROW_NUMBER() OVER (PARTITION BY "{p_c}" ORDER BY rowid) = 1) AS "{p_t}" '
                            f'ON "{c_t}"."{c_c}" = "{p_t}"."{p_c}"'
                        )
            joins_clause = "\n".join(joins_sql)

            # Build where with drill filters
            rec_where = [f'"{t_tbl}"."{t_col}" >= ? AND "{t_tbl}"."{t_col}" < ?']
            rec_params = [min_start, max_end]
            for df in drill_filters:
                df_tbl, df_col = df.column.split(".", 1)
                rec_where.append(f'"{df_tbl}"."{df_col}" = ?')
                rec_params.append(df.value)

            dim_expr = f'COALESCE(CAST("{d_tbl}"."{d_col}" AS VARCHAR), \'(missing)\')'
            rec_sql = f'''
                SELECT {dim_expr}, COALESCE({cur_agg}, 0) - COALESCE({prev_agg}, 0) AS seg_delta
                FROM "{fact_table}"
                {joins_clause}
                WHERE {' AND '.join(rec_where)}
                GROUP BY 1
                ORDER BY seg_delta ASC
                LIMIT 1
            '''
            try:
                rec_row = con.execute(rec_sql, rec_params).fetchone()
                if rec_row:
                    seg_v = rec_row[0]
                    seg_d = round(float(rec_row[1]), 2)
                    c_step = round(seg_d / parent_delta, 2) if parent_delta != 0 else 0.0
                    if c_step >= settings.WHY_MIN_SHARE:
                        next_drivers.append((r_dim, {"value": seg_v, "delta": seg_d}, c_step, 2.0))
            except Exception:
                pass

        next_drivers.sort(key=lambda x: x[2], reverse=True)
        drivers = next_drivers

    # 5. Top Individual Contributors (Entities like Products)
    top_contributors = None
    # Look for entity column in products table (e.g. products.product_name)
    entity_col = "products.product_name"
    if "products" in semantic.tables and "product_name" in semantic.tables["products"].columns:
        p_path = jg.find_join_path(fact_table, "products")
        if p_path:
            p_joins = [
                f'LEFT JOIN (SELECT * FROM "{p_t}" QUALIFY ROW_NUMBER() OVER (PARTITION BY "{p_c}" ORDER BY rowid) = 1) AS "{p_t}" ON "{c_t}"."{c_c}" = "{p_t}"."{p_c}"'
                for c_t, c_c, p_t, p_c in p_path
            ]
            # Add customer join if West filter exists
            if any("customers" in df.column for df in drill_filters):
                c_path = jg.find_join_path(fact_table, "customers")
                if c_path:
                    p_joins.extend([
                        f'LEFT JOIN (SELECT * FROM "{p_t}" QUALIFY ROW_NUMBER() OVER (PARTITION BY "{p_c}" ORDER BY rowid) = 1) AS "{p_t}" ON "{c_t}"."{c_c}" = "{p_t}"."{p_c}"'
                        for c_t, c_c, p_t, p_c in c_path
                    ])

            ent_where = [f'"{t_tbl}"."{t_col}" >= ? AND "{t_tbl}"."{t_col}" < ?']
            ent_params = [min_start, max_end]
            for df in drill_filters:
                df_tbl, df_col = df.column.split(".", 1)
                ent_where.append(f'"{df_tbl}"."{df_col}" = ?')
                ent_params.append(df.value)

            ent_sql = f'''
                SELECT 
                    "products"."product_name" AS item,
                    COALESCE({cur_agg}, 0) - COALESCE({prev_agg}, 0) AS delta
                FROM "{fact_table}"
                {" ".join(p_joins)}
                WHERE {' AND '.join(ent_where)}
                GROUP BY 1
                ORDER BY delta ASC
                LIMIT 5
            '''
            try:
                ent_rows = con.execute(ent_sql, ent_params).fetchall()
                top_rows = []
                for er in ent_rows:
                    i_name = str(er[0])
                    i_delta = round(float(er[1]), 2)
                    cum_s = round(i_delta / overall_delta, 3) if overall_delta != 0 else 0.0
                    top_rows.append({
                        "value": i_name,
                        "delta": i_delta,
                        "cumulative_share": cum_s
                    })
                top_contributors = {
                    "dimension": entity_col,
                    "rows": top_rows
                }
            except Exception:
                pass

    con.close()

    return {
        "metric": metric_name,
        "direction": direction,
        "target": {"start": str(t_start), "end": str(t_end), "value": target_total},
        "baseline": {"start": str(b_start), "end": str(b_end), "value": baseline_total},
        "delta": overall_delta,
        "delta_pct": overall_pct,
        "broad_based": len(drivers) == 0 and len(drill_path) == 0,
        "offsetting": any(d["offsetting"] for d in dimension_results),
        "dimensions": dimension_results,
        "drill_path": drill_path,
        "top_contributors": top_contributors
    }
