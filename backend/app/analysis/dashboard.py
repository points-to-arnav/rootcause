import logging
from datetime import date
from typing import Any, Dict, List, Optional, Tuple
import duckdb
from app.analysis.alerts import generate_alerts
from app.planner.plan_schema import Plan, TimeSpec, LastN, Calendar, Comparison, Sort
from app.planner.timeutil import resolve_time_window, resolve_comparison_window, parse_iso_date
from app.planner.validator import validate_plan
from app.planner.compiler import compile_plan_to_sql
from app.planner.executor import execute_query
from app.semantic.model import SemanticLayer
from app.viz.selector import select_chart

logger = logging.getLogger(__name__)

def generate_sparkline(db_path: str, semantic: SemanticLayer, metric_name: str, anchor_str: str) -> List[float]:
    """Generates 12 monthly data points for a KPI sparkline."""
    try:
        plan = Plan(
            intent="trend",
            metric=metric_name,
            time=TimeSpec(range=LastN(unit="month", n=12), grain="month")
        )
        plan, _, _ = validate_plan(plan, semantic)
        w_start, w_end, _ = resolve_time_window(plan.time.range, anchor_str)
        sql, params = compile_plan_to_sql(plan, semantic, (w_start, w_end))
        res = execute_query(db_path, sql, params)
        return [round(float(r[1]), 2) for r in res.get("rows", []) if r and len(r) > 1 and r[1] is not None]
    except Exception as e:
        logger.debug(f"Failed to generate sparkline for {metric_name}: {e}")
        return []

def _discover_dashboard_dimensions(semantic: SemanticLayer) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Discovers candidate dimensions for dashboard panels.
    Falls back gracefully when retail tables (customers, products) are absent.
    Returns (breakdown_1_dim, breakdown_2_dim, ranking_entity_dim).
    """
    b1_dim = None
    b2_dim = None
    rank_dim = None

    # 1. Preferred defaults if standard retail tables exist
    if "customers" in semantic.tables and "region" in semantic.tables["customers"].columns:
        b1_dim = "customers.region"
    if "products" in semantic.tables and "category" in semantic.tables["products"].columns:
        b2_dim = "products.category"
    if "products" in semantic.tables and "product_name" in semantic.tables["products"].columns:
        rank_dim = "products.product_name"

    # 2. Dynamic discovery for non-retail or custom schemas (e.g. HR, logistics, SaaS)
    candidates_cat = []
    candidates_entity = []

    for tname, tmeta in semantic.tables.items():
        for cname, cmeta in tmeta.columns.items():
            fq = f"{tname}.{cname}"
            if cmeta.role == "dimension" and 2 <= cmeta.distinct <= 40:
                candidates_cat.append((fq, cmeta.display_name))
            elif cmeta.entity or (cmeta.role in ["text", "dimension"] and cmeta.distinct > 10):
                candidates_entity.append((fq, cmeta.display_name))

    if not b1_dim and candidates_cat:
        b1_dim = candidates_cat[0][0]
    if not b2_dim:
        for fq, _ in candidates_cat:
            if fq != b1_dim:
                b2_dim = fq
                break
    if not rank_dim and candidates_entity:
        rank_dim = candidates_entity[0][0]
    elif not rank_dim and candidates_cat:
        for fq, _ in reversed(candidates_cat):
            if fq != b1_dim:
                rank_dim = fq
                break

    return b1_dim, b2_dim, rank_dim

def generate_management_dashboard(
    db_path: str,
    semantic: SemanticLayer
) -> Dict[str, Any]:
    """
    Builds the complete one-prompt management dashboard:
    KPIs + sparklines, monthly trend, top breakdowns, ranking, and alerts.
    Dynamically adapts to anchor year and available table schema.
    """
    anchor_str = semantic.time.anchor_date or "2026-08-31"
    try:
        anchor_year = str(parse_iso_date(anchor_str).year)
    except Exception:
        anchor_year = "2026"

    # Current period: Last 1 complete month
    t_start, t_end, cur_label = resolve_time_window(LastN(unit="month", n=1), anchor_str)
    b_start, b_end, base_label = resolve_comparison_window(t_start, t_end, "previous_period")

    # 1. KPI Cards (prioritize standard metrics, fallback to whatever exists)
    kpis = []
    target_metrics = ["revenue", "orders", "units", "avg_order_value", "return_rate"]
    available_metrics = [m for m in semantic.metrics if m.name in target_metrics]
    if not available_metrics and semantic.metrics:
        available_metrics = semantic.metrics[:5]

    for m in available_metrics:
        try:
            plan = Plan(
                intent="kpi",
                metric=m.name,
                time=TimeSpec(range=LastN(unit="month", n=1)),
                comparison=Comparison(type="previous_period")
            )
            plan, _, _ = validate_plan(plan, semantic)
            sql, params = compile_plan_to_sql(plan, semantic, (t_start, t_end), (b_start, b_end))
            res = execute_query(db_path, sql, params)

            if res.get("rows"):
                r = res["rows"][0]
                sparkline = generate_sparkline(db_path, semantic, m.name, anchor_str)
                kpis.append({
                    "metric": m.name,
                    "label": m.label,
                    "value": r[res["columns"].index("current")],
                    "previous": r[res["columns"].index("previous")],
                    "delta": r[res["columns"].index("delta")],
                    "delta_pct": r[res["columns"].index("delta_pct")],
                    "value_format": m.format,
                    "sparkline": sparkline
                })
        except Exception as e:
            logger.warning(f"Error computing KPI {m.name}: {e}")
            continue

    # Primary metric for visual panels
    primary_metric = available_metrics[0].name if available_metrics else "revenue"
    primary_metric_obj = next((m for m in semantic.metrics if m.name == primary_metric), None)
    primary_format = primary_metric_obj.format if primary_metric_obj else "currency"
    primary_label = primary_metric_obj.label if primary_metric_obj else primary_metric.replace("_", " ").title()

    # 2. Panels
    panels = []

    # Panel A: Monthly Trend (Dynamically anchored to dataset year)
    try:
        trend_plan = Plan(
            intent="trend",
            metric=primary_metric,
            time=TimeSpec(range=Calendar(unit="year", value=anchor_year), grain="month")
        )
        trend_plan, _, _ = validate_plan(trend_plan, semantic)
        tw_start, tw_end, _ = resolve_time_window(trend_plan.time.range, anchor_str)
        trend_sql, trend_params = compile_plan_to_sql(trend_plan, semantic, (tw_start, tw_end))
        trend_res = execute_query(db_path, trend_sql, trend_params)

        # Fallback if specific calendar year has zero records
        if not trend_res.get("rows"):
            trend_plan.time = TimeSpec(range=LastN(unit="month", n=12), grain="month")
            trend_plan, _, _ = validate_plan(trend_plan, semantic)
            tw_start, tw_end, _ = resolve_time_window(trend_plan.time.range, anchor_str)
            trend_sql, trend_params = compile_plan_to_sql(trend_plan, semantic, (tw_start, tw_end))
            trend_res = execute_query(db_path, trend_sql, trend_params)

        trend_chart = select_chart(trend_plan, trend_res, primary_format)
        panels.append({
            "id": "panel_trend",
            "title": f"{anchor_year} Monthly {primary_label} Trend",
            "plan": trend_plan.model_dump(),
            "sql": trend_sql,
            "result": trend_res,
            "chart": trend_chart,
            "insight": f"Seasonal trend and monthly progression for {primary_label.lower()}."
        })
    except Exception as e:
        logger.warning(f"Error generating Panel A (Trend): {e}")

    # Discover candidate breakdown & ranking dimensions
    b1_dim, b2_dim, rank_dim = _discover_dashboard_dimensions(semantic)

    # Panel B: Breakdown 1 (with MoM comparison)
    if b1_dim:
        try:
            b1_tbl, b1_col = b1_dim.split(".", 1)
            b1_disp = semantic.tables[b1_tbl].columns[b1_col].display_name if b1_tbl in semantic.tables and b1_col in semantic.tables[b1_tbl].columns else b1_col.replace("_", " ").title()
            b1_plan = Plan(
                intent="breakdown",
                metric=primary_metric,
                dimensions=[b1_dim],
                time=TimeSpec(range=LastN(unit="month", n=1)),
                comparison=Comparison(type="previous_period")
            )
            b1_plan, _, _ = validate_plan(b1_plan, semantic)
            b1_sql, b1_params = compile_plan_to_sql(b1_plan, semantic, (t_start, t_end), (b_start, b_end))
            b1_res = execute_query(db_path, b1_sql, b1_params)
            b1_chart = select_chart(b1_plan, b1_res, primary_format)
            panels.append({
                "id": "panel_breakdown_1",
                "title": f"{primary_label} by {b1_disp} ({cur_label} vs {base_label})",
                "plan": b1_plan.model_dump(),
                "sql": b1_sql,
                "result": b1_res,
                "chart": b1_chart,
                "insight": f"{b1_disp} segment performance comparison highlighting leading and lagging groups."
            })
        except Exception as e:
            logger.warning(f"Error generating Panel B: {e}")

    # Panel C: Breakdown 2 (with MoM comparison)
    if b2_dim:
        try:
            b2_tbl, b2_col = b2_dim.split(".", 1)
            b2_disp = semantic.tables[b2_tbl].columns[b2_col].display_name if b2_tbl in semantic.tables and b2_col in semantic.tables[b2_tbl].columns else b2_col.replace("_", " ").title()
            b2_plan = Plan(
                intent="breakdown",
                metric=primary_metric,
                dimensions=[b2_dim],
                time=TimeSpec(range=LastN(unit="month", n=1)),
                comparison=Comparison(type="previous_period")
            )
            b2_plan, _, _ = validate_plan(b2_plan, semantic)
            b2_sql, b2_params = compile_plan_to_sql(b2_plan, semantic, (t_start, t_end), (b_start, b_end))
            b2_res = execute_query(db_path, b2_sql, b2_params)
            b2_chart = select_chart(b2_plan, b2_res, primary_format)
            panels.append({
                "id": "panel_breakdown_2",
                "title": f"{primary_label} by {b2_disp} ({cur_label} vs {base_label})",
                "plan": b2_plan.model_dump(),
                "sql": b2_sql,
                "result": b2_res,
                "chart": b2_chart,
                "insight": f"{b2_disp} breakdown showing categorical revenue distribution."
            })
        except Exception as e:
            logger.warning(f"Error generating Panel C: {e}")

    # Panel D: Entity Ranking (Top 10)
    if rank_dim:
        try:
            r_tbl, r_col = rank_dim.split(".", 1)
            r_disp = semantic.tables[r_tbl].columns[r_col].display_name if r_tbl in semantic.tables and r_col in semantic.tables[r_tbl].columns else r_col.replace("_", " ").title()
            rank_plan = Plan(
                intent="ranking",
                metric=primary_metric,
                dimensions=[rank_dim],
                time=TimeSpec(range=LastN(unit="month", n=1)),
                limit=10
            )
            rank_plan, _, _ = validate_plan(rank_plan, semantic)
            rank_sql, rank_params = compile_plan_to_sql(rank_plan, semantic, (t_start, t_end))
            rank_res = execute_query(db_path, rank_sql, rank_params)
            rank_chart = select_chart(rank_plan, rank_res, primary_format)
            panels.append({
                "id": "panel_ranking",
                "title": f"Top 10 {r_disp} by {primary_label} ({cur_label})",
                "plan": rank_plan.model_dump(),
                "sql": rank_sql,
                "result": rank_res,
                "chart": rank_chart,
                "insight": f"Top contributors ranked for the current period."
            })
        except Exception as e:
            logger.warning(f"Error generating Panel D: {e}")

    # 3. Alerts
    alerts = generate_alerts(db_path, semantic, kpis, cur_label)

    # 4. Executive Summary
    lead_kpi = next((k for k in kpis if k["metric"] == primary_metric), (kpis[0] if kpis else None))
    if lead_kpi and lead_kpi.get("delta_pct") is not None:
        val = lead_kpi["value"]
        dp = lead_kpi["delta_pct"]
        dir_w = "fell" if dp < 0 else "rose"
        unit_sym = "$" if primary_format == "currency" else ""
        summary = (
            f"Business Overview for {cur_label}: {primary_label} reached {unit_sym}{val:,.2f}, which {dir_w} by {abs(dp)}% "
            f"compared to {base_label}. "
        )
        if alerts:
            summary += f"Identified {len(alerts)} alert{'s' if len(alerts) > 1 else ''} requiring operational attention, including {alerts[0]['title']}."
        else:
            summary += "Performance remains stable across major business dimensions."
    else:
        summary = f"Performance dashboard generated for {cur_label} across {len(panels)} operational panels."

    return {
        "status": "ok",
        "summary": summary,
        "period": {"label": cur_label, "baseline_label": base_label},
        "kpis": kpis,
        "panels": panels,
        "alerts": alerts,
        "dq_warnings": semantic.quality_issues[:5]
    }

