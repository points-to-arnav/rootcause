from typing import Any, Dict, List, Optional
from app.planner.plan_schema import Plan

def select_chart(
    plan: Plan,
    result: Dict[str, Any],
    metric_format: str = "currency"
) -> Dict[str, Any]:
    """
    Deterministically maps result shape and plan intent to an ECharts option or KPI payload.
    Returns: { "type": str, "value_format": str, "echarts_option": dict, "kpi": dict | None }
    """
    columns = result.get("columns", [])
    rows = result.get("rows", [])
    row_count = len(rows)

    # 1. Why intent -> Contribution Chart
    if plan.intent == "why":
        return {
            "type": "contribution",
            "value_format": "percent",
            "echarts_option": None,
            "kpi": None
        }

    # 2. KPI / Single Value
    if plan.intent == "kpi":
        if "delta" in columns and row_count >= 1:
            r = rows[0]
            c_idx = columns.index("current")
            p_idx = columns.index("previous")
            d_idx = columns.index("delta")
            dp_idx = columns.index("delta_pct")
            return {
                "type": "kpi",
                "value_format": metric_format,
                "kpi": {
                    "value": r[c_idx],
                    "previous": r[p_idx],
                    "delta": r[d_idx],
                    "delta_pct": r[dp_idx]
                },
                "echarts_option": None
            }
        elif row_count == 1 and len(columns) == 1:
            return {
                "type": "kpi",
                "value_format": metric_format,
                "kpi": {
                    "value": rows[0][0],
                    "previous": None,
                    "delta": None,
                    "delta_pct": None
                },
                "echarts_option": None
            }

    # 3. Empty result or Table
    if row_count == 0 or plan.intent == "detail" or len(columns) > 5:
        return {
            "type": "table",
            "value_format": metric_format,
            "echarts_option": None,
            "kpi": None
        }

    # 4. Trend (Time + Metric)
    if plan.intent == "trend" or ("period" in columns and len(columns) == 2):
        x_data = [str(r[0]) for r in rows]
        y_data = [r[1] for r in rows]
        option = {
            "tooltip": {"trigger": "axis"},
            "grid": {"left": "3%", "right": "4%", "bottom": "3%", "containLabel": True},
            "xAxis": {"type": "category", "data": x_data, "axisLabel": {"rotate": 30 if len(x_data) > 8 else 0}},
            "yAxis": {"type": "value"},
            "series": [{
                "name": columns[1].replace("_", " ").title(),
                "type": "line",
                "data": y_data,
                "smooth": True,
                "itemStyle": {"color": "#3B82F6"},
                "areaStyle": {"color": "rgba(59, 130, 246, 0.1)"}
            }]
        }
        return {
            "type": "line",
            "value_format": metric_format,
            "echarts_option": option,
            "kpi": None
        }

    # 5. Comparison by Dimension (Grouped Bar)
    if "current" in columns and "previous" in columns and len(columns) >= 3:
        dim_name = columns[0]
        categories = [str(r[0]) for r in rows]
        cur_vals = [r[columns.index("current")] for r in rows]
        prev_vals = [r[columns.index("previous")] for r in rows]

        option = {
            "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
            "legend": {"data": ["Current", "Previous"]},
            "grid": {"left": "3%", "right": "4%", "bottom": "3%", "containLabel": True},
            "xAxis": {"type": "category", "data": categories},
            "yAxis": {"type": "value"},
            "series": [
                {"name": "Previous", "type": "bar", "data": prev_vals, "itemStyle": {"color": "#94A3B8"}},
                {"name": "Current", "type": "bar", "data": cur_vals, "itemStyle": {"color": "#3B82F6"}}
            ]
        }
        return {
            "type": "grouped_bar",
            "value_format": metric_format,
            "echarts_option": option,
            "kpi": None
        }

    # 6. Breakdown / Ranking (Bar or Horizontal Bar)
    if len(columns) == 2:
        categories = [str(r[0]) for r in rows]
        values = [r[1] for r in rows]

        # Use horizontal bar if ranking, >10 categories, or long labels
        has_long_labels = any(len(c) > 16 for c in categories)
        use_horizontal = (plan.intent == "ranking" or len(categories) > 10 or has_long_labels)

        if use_horizontal:
            # Reverse so highest is at top
            categories_rev = list(reversed(categories))
            values_rev = list(reversed(values))
            option = {
                "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
                "grid": {"left": "3%", "right": "6%", "bottom": "3%", "containLabel": True},
                "xAxis": {"type": "value"},
                "yAxis": {"type": "category", "data": categories_rev},
                "series": [{
                    "type": "bar",
                    "data": values_rev,
                    "itemStyle": {"color": "#3B82F6", "borderRadius": [0, 4, 4, 0]}
                }]
            }
            return {
                "type": "bar_h",
                "value_format": metric_format,
                "echarts_option": option,
                "kpi": None
            }
        else:
            option = {
                "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
                "grid": {"left": "3%", "right": "4%", "bottom": "3%", "containLabel": True},
                "xAxis": {"type": "category", "data": categories},
                "yAxis": {"type": "value"},
                "series": [{
                    "type": "bar",
                    "data": values,
                    "itemStyle": {"color": "#3B82F6", "borderRadius": [4, 4, 0, 0]}
                }]
            }
            return {
                "type": "bar",
                "value_format": metric_format,
                "echarts_option": option,
                "kpi": None
            }

    # Default to table
    return {
        "type": "table",
        "value_format": metric_format,
        "echarts_option": None,
        "kpi": None
    }
