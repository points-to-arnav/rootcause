from typing import Any, Dict, List, Optional
from app.planner.plan_schema import Plan

# Categorical palette from viz-rules.md (colour-blind safe); "Other" is grey.
_PALETTE = ["#4C78A8", "#F58518", "#54A24B", "#B279A2", "#9D755D", "#72B7B2"]
_OTHER_COLOUR = "#BAB0AC"
MAX_SERIES = 6


def _table(metric_format: str) -> Dict[str, Any]:
    return {"type": "table", "value_format": metric_format, "echarts_option": None, "kpi": None}


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _bar_chart(
    categories: List[str], values: List[Any], metric_format: str, horizontal: bool
) -> Dict[str, Any]:
    """A single-series bar chart. Order is kept exactly as given: a sorted breakdown
    stays sorted, and a time series stays chronological."""
    if horizontal:
        # ECharts draws the first category at the bottom; reverse so it is on top.
        option = {
            "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
            "grid": {"left": "3%", "right": "6%", "bottom": "3%", "containLabel": True},
            "xAxis": {"type": "value"},
            "yAxis": {"type": "category", "data": list(reversed(categories))},
            "series": [{
                "type": "bar",
                "data": list(reversed(values)),
                "itemStyle": {"color": "#3B82F6", "borderRadius": [0, 4, 4, 0]},
            }],
        }
        return {"type": "bar_h", "value_format": metric_format, "echarts_option": option, "kpi": None}

    option = {
        "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
        "grid": {"left": "3%", "right": "4%", "bottom": "3%", "containLabel": True},
        "xAxis": {"type": "category", "data": categories,
                  "axisLabel": {"rotate": 30 if len(categories) > 8 else 0}},
        "yAxis": {"type": "value"},
        "series": [{
            "type": "bar",
            "data": values,
            "itemStyle": {"color": "#3B82F6", "borderRadius": [4, 4, 0, 0]},
        }],
    }
    return {"type": "bar", "value_format": metric_format, "echarts_option": option, "kpi": None}


def _series_by_dimension(
    rows: List[List[Any]],
    metric_format: str,
    as_bars: bool,
    additive: bool,
) -> Optional[Dict[str, Any]]:
    """
    A result of (period, dimension, measure) rows: one series per dimension value
    over the periods. Returns None when there are too many series to read and they
    cannot be folded into "Other" (a non-additive measure cannot be summed).
    """
    # Decide once, for the whole result, which column is the measure: the compiler
    # emits it last, but a NULL measure in one row must not make a row's dimension
    # text look like the measure. The numeric column wins; a tie means the last one.
    numeric_in_middle = sum(1 for r in rows if _is_number(r[1]))
    numeric_in_last = sum(1 for r in rows if _is_number(r[2]))
    value_idx, label_idx = (2, 1) if numeric_in_last >= numeric_in_middle else (1, 2)

    periods: List[str] = []
    seen_periods = set()
    cells: Dict[str, Dict[str, Any]] = {}

    for row in rows:
        period = str(row[0])
        label = row[label_idx]
        group = "(missing)" if label is None else str(label)
        if period not in seen_periods:
            seen_periods.add(period)
            periods.append(period)
        cells.setdefault(group, {})[period] = row[value_idx]

    totals = {g: sum(v for v in c.values() if _is_number(v)) for g, c in cells.items()}
    names = sorted(cells, key=lambda g: totals[g], reverse=True)

    if len(names) > MAX_SERIES:
        if not additive:
            return None
        rest = names[MAX_SERIES - 1:]
        names = names[:MAX_SERIES - 1]
        cells["Other"] = {
            p: sum(cells[g].get(p, 0) or 0 for g in rest if _is_number(cells[g].get(p))) for p in periods
        }
        names.append("Other")

    series = []
    for index, name in enumerate(names):
        colour = _OTHER_COLOUR if name == "Other" else _PALETTE[index % len(_PALETTE)]
        entry: Dict[str, Any] = {
            "name": name,
            "type": "bar" if as_bars else "line",
            "data": [cells[name].get(p) for p in periods],
            "itemStyle": {"color": colour},
        }
        if as_bars:
            entry["itemStyle"]["borderRadius"] = [2, 2, 0, 0]
        else:
            entry["smooth"] = False
            entry["lineStyle"] = {"color": colour}
        series.append(entry)

    option = {
        "tooltip": {"trigger": "axis", **({"axisPointer": {"type": "shadow"}} if as_bars else {})},
        "legend": {"top": 0, "data": names},
        "grid": {"left": "3%", "right": "4%", "top": 32, "bottom": "3%", "containLabel": True},
        "xAxis": {"type": "category", "data": periods, "axisLabel": {"rotate": 30 if len(periods) > 8 else 0}},
        "yAxis": {"type": "value"},
        "series": series,
    }
    return {
        "type": "bar" if as_bars else "line",
        "value_format": metric_format,
        "echarts_option": option,
        "kpi": None,
    }


def select_chart(
    plan: Plan,
    result: Dict[str, Any],
    metric_format: str = "currency",
    requested: Optional[str] = None,
    additive: bool = True,
) -> Dict[str, Any]:
    """
    Deterministically maps result shape and plan intent to an ECharts option or KPI payload.
    Returns: { "type": str, "value_format": str, "echarts_option": dict, "kpi": dict | None }

    `requested` is the chart type the user asked for in their own words ("bar",
    "bar_h", "line" or "table", see viz/chart_request.py). It is honoured whenever
    the result's shape can carry it and ignored when it cannot - a single figure is
    not a bar chart, a breakdown by region is not a time series - and the caller
    tells the user which happened.
    """
    columns = result.get("columns", [])
    rows = result.get("rows", [])
    row_count = len(rows)
    has_comparison = "current" in columns and "previous" in columns

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

    # 3. Empty result or Table (also when the user asked for one)
    if row_count == 0 or plan.intent == "detail" or len(columns) > 5 or requested == "table":
        return _table(metric_format)

    wants_bars = requested in ("bar", "bar_h")

    # 4. Trend (Time + Metric), or Time + Dimension + Metric as one series per value
    time_shaped = plan.intent == "trend" or "period" in columns
    if time_shaped and len(columns) == 2:
        x_data = [str(r[0]) for r in rows]
        y_data = [r[1] for r in rows]

        if wants_bars:
            return _bar_chart(x_data, y_data, metric_format, horizontal=(requested == "bar_h"))

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

    if time_shaped and len(columns) == 3 and not has_comparison:
        chart = _series_by_dimension(rows, metric_format, as_bars=wants_bars, additive=additive)
        return chart if chart is not None else _table(metric_format)

    # 5. Comparison by Dimension (Grouped Bar)
    if has_comparison and len(columns) >= 3:
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

        # Use horizontal bar if ranking, >10 categories, or long labels - or if the
        # user asked for horizontal bars.
        has_long_labels = any(len(c) > 16 for c in categories)
        use_horizontal = (
            requested == "bar_h"
            or plan.intent == "ranking"
            or len(categories) > 10
            or has_long_labels
        )
        return _bar_chart(categories, values, metric_format, horizontal=use_horizontal)

    # Default to table
    return _table(metric_format)
