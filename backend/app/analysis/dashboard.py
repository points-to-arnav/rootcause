from datetime import date
from typing import Any, Dict, List, Optional
import duckdb
from app.analysis.alerts import generate_alerts
from app.planner.plan_schema import Plan, TimeSpec, LastN, Calendar, Comparison, Sort
from app.planner.timeutil import resolve_time_window, resolve_comparison_window
from app.planner.validator import validate_plan
from app.planner.compiler import compile_plan_to_sql
from app.planner.executor import execute_query
from app.semantic.model import SemanticLayer
from app.viz.selector import select_chart

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
        return [round(float(r[1]), 2) for r in res["rows"] if r[1] is not None]
    except Exception:
        return []

def generate_management_dashboard(
    db_path: str,
    semantic: SemanticLayer
) -> Dict[str, Any]:
    """
    Builds the complete one-prompt management dashboard:
    KPIs + sparklines, monthly trend, top breakdowns, ranking, and alerts.
    """
    anchor_str = semantic.time.anchor_date or "2026-08-31"

    # Current period: Last 1 complete month
    t_start, t_end, cur_label = resolve_time_window(LastN(unit="month", n=1), anchor_str)
    b_start, b_end, base_label = resolve_comparison_window(t_start, t_end, "previous_period")

    # 1. KPI Cards (up to 5 default metrics)
    kpis = []
    target_metrics = ["revenue", "orders", "units", "avg_order_value", "return_rate"]
    available_metrics = [m for m in semantic.metrics if m.name in target_metrics]

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

            if res["rows"]:
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
        except Exception:
            continue

    # 2. Panels

    # Panel A: Monthly Trend (Full time range)
    trend_plan = Plan(
        intent="trend",
        metric="revenue",
        time=TimeSpec(range=Calendar(unit="year", value="2026"), grain="month")
    )
    trend_plan, _, _ = validate_plan(trend_plan, semantic)
    tw_start, tw_end, _ = resolve_time_window(trend_plan.time.range, anchor_str)
    trend_sql, trend_params = compile_plan_to_sql(trend_plan, semantic, (tw_start, tw_end))
    trend_res = execute_query(db_path, trend_sql, trend_params)
    trend_chart = select_chart(trend_plan, trend_res, "currency")

    panels = [{
        "id": "panel_trend",
        "title": "2026 Monthly Revenue Trend",
        "plan": trend_plan.model_dump(),
        "sql": trend_sql,
        "result": trend_res,
        "chart": trend_chart,
        "insight": "Shows seasonal trend and monthly progression across 2026."
    }]

    # Panel B: Breakdown 1 (e.g. Region with MoM comparison)
    if "customers" in semantic.tables and "region" in semantic.tables["customers"].columns:
        b1_plan = Plan(
            intent="breakdown",
            metric="revenue",
            dimensions=["customers.region"],
            time=TimeSpec(range=LastN(unit="month", n=1)),
            comparison=Comparison(type="previous_period")
        )
        b1_plan, _, _ = validate_plan(b1_plan, semantic)
        b1_sql, b1_params = compile_plan_to_sql(b1_plan, semantic, (t_start, t_end), (b_start, b_end))
        b1_res = execute_query(db_path, b1_sql, b1_params)
        b1_chart = select_chart(b1_plan, b1_res, "currency")
        panels.append({
            "id": "panel_breakdown_region",
            "title": f"Revenue by Region ({cur_label} vs {base_label})",
            "plan": b1_plan.model_dump(),
            "sql": b1_sql,
            "result": b1_res,
            "chart": b1_chart,
            "insight": "Regional performance comparison highlighting leading and lagging territories."
        })

    # Panel C: Breakdown 2 (e.g. Category with MoM comparison)
    if "products" in semantic.tables and "category" in semantic.tables["products"].columns:
        b2_plan = Plan(
            intent="breakdown",
            metric="revenue",
            dimensions=["products.category"],
            time=TimeSpec(range=LastN(unit="month", n=1)),
            comparison=Comparison(type="previous_period")
        )
        b2_plan, _, _ = validate_plan(b2_plan, semantic)
        b2_sql, b2_params = compile_plan_to_sql(b2_plan, semantic, (t_start, t_end), (b_start, b_end))
        b2_res = execute_query(db_path, b2_sql, b2_params)
        b2_chart = select_chart(b2_plan, b2_res, "currency")
        panels.append({
            "id": "panel_breakdown_category",
            "title": f"Revenue by Category ({cur_label} vs {base_label})",
            "plan": b2_plan.model_dump(),
            "sql": b2_sql,
            "result": b2_res,
            "chart": b2_chart,
            "insight": "Product category revenue split showing category momentum."
        })

    # Panel D: Top 10 Products Ranking
    if "products" in semantic.tables and "product_name" in semantic.tables["products"].columns:
        rank_plan = Plan(
            intent="ranking",
            metric="revenue",
            dimensions=["products.product_name"],
            time=TimeSpec(range=LastN(unit="month", n=1)),
            limit=10
        )
        rank_plan, _, _ = validate_plan(rank_plan, semantic)
        rank_sql, rank_params = compile_plan_to_sql(rank_plan, semantic, (t_start, t_end))
        rank_res = execute_query(db_path, rank_sql, rank_params)
        rank_chart = select_chart(rank_plan, rank_res, "currency")
        panels.append({
            "id": "panel_ranking_products",
            "title": f"Top 10 Products by Revenue ({cur_label})",
            "plan": rank_plan.model_dump(),
            "sql": rank_sql,
            "result": rank_res,
            "chart": rank_chart,
            "insight": "Top revenue-generating individual items for the current period."
        })

    # 3. Alerts
    alerts = generate_alerts(db_path, semantic, kpis, cur_label)

    # 4. Executive Summary
    rev_kpi = next((k for k in kpis if k["metric"] == "revenue"), None)
    if rev_kpi and rev_kpi.get("delta_pct") is not None:
        val = rev_kpi["value"]
        dp = rev_kpi["delta_pct"]
        dir_w = "fell" if dp < 0 else "rose"
        summary = (
            f"Business Overview for {cur_label}: Total revenue reached ${val:,.2f}, which {dir_w} by {abs(dp)}% "
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
