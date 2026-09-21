"""
Chart type follows what the user asked for, and multi-series results are drawn
as series - not as a line through a column of text.

Three layers: the wording parser, the selector, and the whole pipeline with a
stubbed planner (so no LLM is involved).
"""
import os

import pandas as pd
import pytest

import app.pipeline as pipeline
from app.api.routes_datasets import process_and_save_dataset
from app.config import settings
from app.memory.session import create_session
from app.planner.plan_schema import Plan, PlannerOutput, TimeSpec
from app.viz.chart_request import chart_request_note, parse_chart_request
from app.viz.selector import select_chart

# --------------------------------------------------------------------------- parser


@pytest.mark.parametrize("question, expected", [
    ("show me the bargraph by month", "bar"),
    ("show me the bar graph by month", "bar"),
    ("show me a Bar-Chart of spend", "bar"),
    ("cloud spend by month as a bar chart", "bar"),
    ("make it a bar graph", "bar"),
    ("show it in bars", "bar"),
    ("column chart please", "bar"),
    ("horizontal bar chart of revenue by region", "bar_h"),
    ("make it a horizontal bar graph", "bar_h"),
    ("show me a line graph of revenue", "line"),
    ("as a line chart", "line"),
    ("show this as a table", "table"),
    ("give me a table of revenue by region", "table"),
    ("make it a bar graph not a line graph", "bar"),
    ("instead of the bar chart show a line chart", "line"),
    ("no idea, show a bar chart", "bar"),
    ("show revenue by month", None),
    ("what is the total revenue", None),
    ("top 5 products by revenue", None),
    ("show me the sales table", None),
    ("what's the bar tab total", None),
    ("", None),
])
def test_parse_chart_request(question, expected):
    request = parse_chart_request(question)
    assert (request.kind if request else None) == expected


@pytest.mark.parametrize("question, name", [
    ("make a pie chart of revenue by region", "Pie"),
    ("can you make a scatterplot of the above graph", "Scatter"),
    ("show it as a donut", "Donut"),
])
def test_unavailable_types_become_a_bar_request_with_a_note(question, name):
    request = parse_chart_request(question)
    assert request.kind == "bar"
    assert name in request.note and "aren't available" in request.note


def test_note_only_when_the_request_was_not_honoured():
    bar = parse_chart_request("bar graph")
    assert chart_request_note(bar, "bar") is None
    assert chart_request_note(bar, "bar_h") is None          # a horizontal bar is a bar graph
    assert chart_request_note(bar, "contribution") is None   # a why chart is drawn as bars
    assert "instead of a bar chart" in chart_request_note(bar, "kpi")
    assert "instead of a line chart" in chart_request_note(parse_chart_request("line chart"), "bar")


# ------------------------------------------------------------------------- selector

TREND = Plan(intent="trend", metric="spend", time=TimeSpec(grain="month"))
BREAKDOWN = Plan(intent="breakdown", metric="spend", dimensions=["t.tier"])
MONTHS = [["2025-01-01", 10.0], ["2025-02-01", 20.0], ["2025-03-01", 15.0]]


def _trend(rows=MONTHS):
    return {"columns": ["period", "spend"], "rows": rows, "row_count": len(rows)}


def test_default_trend_is_still_a_line():
    assert select_chart(TREND, _trend())["type"] == "line"


def test_trend_asked_as_bars_is_a_bar_chart_in_chronological_order():
    chart = select_chart(TREND, _trend(), requested="bar")
    assert chart["type"] == "bar"
    assert chart["echarts_option"]["xAxis"]["data"] == ["2025-01-01", "2025-02-01", "2025-03-01"]
    assert chart["echarts_option"]["series"][0]["data"] == [10.0, 20.0, 15.0]
    assert chart["echarts_option"]["series"][0]["type"] == "bar"


def test_trend_asked_as_horizontal_bars_keeps_the_first_period_on_top():
    chart = select_chart(TREND, _trend(), requested="bar_h")
    assert chart["type"] == "bar_h"
    # ECharts draws the first category at the bottom, so the list is reversed.
    assert chart["echarts_option"]["yAxis"]["data"] == ["2025-03-01", "2025-02-01", "2025-01-01"]


def test_a_table_request_wins_over_any_chart():
    assert select_chart(TREND, _trend(), requested="table")["type"] == "table"
    assert select_chart(BREAKDOWN, {"columns": ["tier", "spend"], "rows": [["a", 1]], "row_count": 1}, requested="table")["type"] == "table"


def test_default_breakdown_is_unchanged_and_horizontal_is_honoured():
    result = {"columns": ["tier", "spend"], "rows": [["A", 3], ["B", 2]], "row_count": 2}
    assert select_chart(BREAKDOWN, result)["type"] == "bar"
    assert select_chart(BREAKDOWN, result, requested="bar")["type"] == "bar"
    assert select_chart(BREAKDOWN, result, requested="bar_h")["type"] == "bar_h"


def test_a_line_request_on_a_category_breakdown_is_not_forced():
    result = {"columns": ["tier", "spend"], "rows": [["A", 3], ["B", 2]], "row_count": 2}
    # A line through unordered categories would imply an order that isn't there.
    assert select_chart(BREAKDOWN, result, requested="line")["type"] == "bar"


def test_a_single_figure_stays_a_figure_whatever_is_asked():
    plan = Plan(intent="kpi", metric="spend")
    result = {"columns": ["spend"], "rows": [[42.0]], "row_count": 1}
    assert select_chart(plan, result, requested="bar")["type"] == "kpi"


def test_a_why_answer_stays_a_contribution_chart():
    plan = Plan(intent="why", metric="spend")
    assert select_chart(plan, {"columns": ["s", "d"], "rows": [["a", 1]], "row_count": 1}, requested="bar")["type"] == "contribution"


def _by_tier(tiers=("A", "B"), months=("2025-01-01", "2025-02-01")):
    rows = [[m, t, float(10 * (i + 1) + j)] for j, m in enumerate(months) for i, t in enumerate(tiers)]
    return {"columns": ["period", "tier", "spend"], "rows": rows, "row_count": len(rows)}


def test_period_by_dimension_becomes_one_series_per_value_not_a_line_through_text():
    """The 3-column result behind 'show me the bargraph by month' after a breakdown."""
    result = _by_tier(("A", "B", "C"))
    line = select_chart(TREND, result)
    bars = select_chart(TREND, result, requested="bar")

    assert line["type"] == "line" and bars["type"] == "bar"
    for chart, kind in ((line, "line"), (bars, "bar")):
        series = chart["echarts_option"]["series"]
        assert sorted(s["name"] for s in series) == ["A", "B", "C"]
        assert all(s["type"] == kind for s in series)
        assert chart["echarts_option"]["xAxis"]["data"] == ["2025-01-01", "2025-02-01"]
        # Every plotted value is the measure, never the dimension's text.
        assert all(isinstance(v, float) for s in series for v in s["data"])


def test_series_values_line_up_with_their_period():
    chart = select_chart(TREND, _by_tier(("A", "B")))
    by_name = {s["name"]: s["data"] for s in chart["echarts_option"]["series"]}
    assert by_name["A"] == [10.0, 11.0] and by_name["B"] == [20.0, 21.0]


def test_a_null_measure_does_not_turn_the_dimension_into_the_measure():
    result = _by_tier(("A", "B"))
    result["rows"][1][2] = None
    chart = select_chart(TREND, result)
    by_name = {s["name"]: s["data"] for s in chart["echarts_option"]["series"]}
    assert by_name["B"] == [None, 21.0]
    assert "A" in by_name and "B" in by_name


def test_more_than_six_series_fold_into_other_when_the_measure_is_additive():
    tiers = tuple(f"T{i}" for i in range(9))
    chart = select_chart(TREND, _by_tier(tiers), additive=True)
    names = [s["name"] for s in chart["echarts_option"]["series"]]
    assert len(names) == 6 and names[-1] == "Other"
    # Nothing is dropped: the folded series carries the sum of the four smallest.
    other = chart["echarts_option"]["series"][-1]["data"]
    all_rows = _by_tier(tiers)["rows"]
    smallest = sorted({r[1] for r in all_rows}, key=lambda t: sum(r[2] for r in all_rows if r[1] == t))[:4]
    assert other[0] == sum(r[2] for r in all_rows if r[1] in smallest and r[0] == "2025-01-01")


def test_more_than_six_series_of_a_non_additive_measure_become_a_table():
    tiers = tuple(f"T{i}" for i in range(9))
    assert select_chart(TREND, _by_tier(tiers), additive=False)["type"] == "table"


def test_a_comparison_with_a_time_column_is_not_read_as_series():
    result = {"columns": ["period", "current", "previous"], "rows": [["x", 2, 1]], "row_count": 1}
    assert select_chart(TREND, result)["type"] == "grouped_bar"


# ------------------------------------------------------------------------- pipeline

TIERS = ["CORE", "EDGE", "DATA"]


@pytest.fixture()
def cloud(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "DATA_DIR", str(tmp_path))
    days = pd.date_range("2025-01-01", periods=120, freq="D")
    rows = [
        {"metric_id": f"M{i:05d}", "recorded_date": d.strftime("%Y-%m-%d"),
         "service_tier": TIERS[i % 3], "cloud_spend_usd": round(50 + (i % 17) * 3.1, 2)}
        for i, d in enumerate(days)
    ]
    csv = tmp_path / "usage.csv"
    pd.DataFrame(rows).to_csv(csv, index=False)
    semantic = process_and_save_dataset("ds_chart", [str(csv)])
    monkeypatch.setattr(pipeline, "narrate_result", lambda **kwargs: "stub narrative")
    return semantic


def _ask(semantic, question, planner_output, session=None):
    """Runs the real pipeline with the planner replaced by a fixed answer."""
    pipeline._DEMO_QUERY_CACHE.clear()
    session = session or create_session("ds_chart")
    original = pipeline.plan_query
    pipeline.plan_query = lambda **kwargs: planner_output
    try:
        return pipeline.run_ask_pipeline(session, semantic, question, None), session
    finally:
        pipeline.plan_query = original


MONTHLY = Plan(intent="trend", metric="cloud_spend_usd", time=TimeSpec(grain="month"))


def test_asking_for_a_bar_graph_by_month_returns_a_bar_chart(cloud):
    response, _ = _ask(cloud, "show me the bargraph by month", PlannerOutput(plan=MONTHLY))

    assert response["status"] == "ok"
    assert response["chart"]["type"] == "bar"
    assert response["result"]["columns"] == ["period", "cloud_spend_usd"]
    assert response["result"]["row_count"] == 4          # Jan-Apr, one bar each
    assert not any("chart" in a.lower() for a in response["assumptions"])


def test_the_same_question_without_the_words_is_still_a_line(cloud):
    response, _ = _ask(cloud, "show me spend by month", PlannerOutput(plan=MONTHLY))
    assert response["chart"]["type"] == "line"


def test_a_follow_up_chart_request_keeps_the_previous_data(cloud):
    _, session = _ask(cloud, "spend by month", PlannerOutput(plan=MONTHLY))
    response, _ = _ask(
        cloud, "make it a bar graph",
        PlannerOutput(is_follow_up=True, changes={}), session=session,
    )
    assert response["chart"]["type"] == "bar"
    assert response["result"]["columns"] == ["period", "cloud_spend_usd"]


def test_bars_by_month_after_a_tier_breakdown_replaces_the_grouping(cloud):
    """The reported case: 'by month' after 'by service tier' must not stay by tier."""
    breakdown = Plan(intent="breakdown", metric="cloud_spend_usd", dimensions=["cloud_service_metrics_x.service_tier"])
    table = next(iter(cloud.tables))
    breakdown.dimensions = [f"{table}.service_tier"]
    _, session = _ask(cloud, "spend by service tier", PlannerOutput(plan=breakdown))

    response, _ = _ask(
        cloud, "show me the bargraph by month",
        PlannerOutput(is_follow_up=True, changes={
            "intent": "trend", "dimensions": None,
            "time": {"grain": "month"}, "sort": {"by": "time", "dir": "asc"},
        }),
        session=session,
    )
    assert response["chart"]["type"] == "bar"
    assert response["result"]["columns"] == ["period", "cloud_spend_usd"]
    assert response["plan"]["dimensions"] == []


def test_a_period_by_tier_result_is_drawn_as_series(cloud):
    table = next(iter(cloud.tables))
    plan = Plan(intent="trend", metric="cloud_spend_usd", dimensions=[f"{table}.service_tier"],
                time=TimeSpec(grain="month"))
    response, _ = _ask(cloud, "spend by month and tier as a bar graph", PlannerOutput(plan=plan))

    assert response["chart"]["type"] == "bar"
    series = response["chart"]["echarts_option"]["series"]
    assert sorted(s["name"] for s in series) == sorted(TIERS)


def test_an_unavailable_type_is_drawn_as_bars_and_the_user_is_told(cloud):
    plan = Plan(intent="breakdown", metric="cloud_spend_usd", dimensions=[f"{next(iter(cloud.tables))}.service_tier"])
    response, _ = _ask(cloud, "a pie chart of spend by tier", PlannerOutput(plan=plan))

    assert response["chart"]["type"] in ("bar", "bar_h")
    assert any("Pie charts aren't available" in a for a in response["assumptions"])


def test_a_chart_request_on_a_single_figure_says_why_it_was_not_drawn(cloud):
    plan = Plan(intent="kpi", metric="cloud_spend_usd")
    response, _ = _ask(cloud, "total spend as a bar graph", PlannerOutput(plan=plan))

    assert response["chart"]["type"] == "kpi"
    assert any("instead of a bar chart" in a for a in response["assumptions"])


def test_asking_for_a_table_returns_a_table(cloud):
    response, _ = _ask(cloud, "show spend by month as a table", PlannerOutput(plan=MONTHLY))
    assert response["chart"]["type"] == "table"
