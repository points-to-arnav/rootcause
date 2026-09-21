"""
"Top N <numeric column> by <other column>" must rank the column the user named, and
a plan that groups by a numeric measure must be refused rather than answered.

Reported case: "Top 10 delay_minutes by Package weight kg (Last 1 month)" produced
a chart of delay *values* as segments, ranked by total package weight - because
delay_minutes was never a metric, the model read the sentence as "rank the
delay_minutes groups by weight", and nothing downstream could tell that was wrong.

These run the real ingestion, validator, compiler and pipeline with the planner
stubbed (no LLM), and compare against independent pandas calculations.
"""
import os

import pandas as pd
import pytest

import app.pipeline as pipeline
from app.api.routes_datasets import process_and_save_dataset
from app.config import settings
from app.memory.session import create_session
from app.narrator.narrator import compute_derived_stats, generate_templated_narrative
from app.planner.compiler import compile_plan_to_sql
from app.planner.executor import execute_query
from app.planner.plan_schema import Plan, PlannerOutput
from app.planner.timeutil import resolve_time_window
from app.planner.validator import validate_plan

TABLE = "shipments"
LAST_MONTH = {"range": {"type": "last_n", "unit": "month", "n": 1}}


def _frame() -> pd.DataFrame:
    days = pd.date_range("2024-10-01", "2024-12-31", freq="D")
    rows = []
    for i in range(2400):
        rows.append({
            "shipment_id": f"SHIP-{i:05d}",
            "dispatch_date": days[i % len(days)].strftime("%Y-%m-%d"),
            "origin_hub": ["Chicago", "Newark", "Dallas", "Denver", "Miami"][i % 5],
            "carrier_name": ["UPS", "FedEx", "DHL", "OnTrac"][(i * 3) % 4],
            "stops": 1 + i % 6,
            "package_weight_kg": round(1 + (i * 7919 % 4000) / 100, 2),
            "shipping_cost_usd": round(20 + (i * 104729 % 9000) / 100, 2),
            # ~95 distinct whole numbers over 2,400 rows (4%), like a real delay column.
            "delay_minutes": (i * 37) % 95,
        })
    frame = pd.DataFrame(rows)
    # Twelve unmistakable December delays, so the top 10 has no ties to argue over.
    december = frame.index[frame["dispatch_date"] >= "2024-12-01"][:12]
    frame.loc[december, "delay_minutes"] = list(range(200, 212))
    return frame


@pytest.fixture()
def fleet(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "DATA_DIR", str(tmp_path))
    frame = _frame()
    csv = tmp_path / f"{TABLE}.csv"
    frame.to_csv(csv, index=False)
    semantic = process_and_save_dataset("ds_fleet", [str(csv)])
    frame["d"] = pd.to_datetime(frame["dispatch_date"])
    return semantic, os.path.join(str(tmp_path), "ds_fleet", "data.duckdb"), frame


def _run(semantic, db_path, plan_dict):
    """validator -> compiler -> executor, returning (sql, result)."""
    plan, errors, notes = validate_plan(Plan.model_validate(plan_dict), semantic)
    assert errors == [], errors
    start, end, _ = resolve_time_window(
        plan.time.range if plan.time else None, semantic.time.anchor_date, semantic.time.min
    )
    sql, params = compile_plan_to_sql(plan, semantic, (start, end))
    return " ".join(sql.split()), execute_query(db_path, sql, params), plan, notes


def _top_records_plan(rank_metric="delay_minutes", show="package_weight_kg", direction="desc", limit=10):
    return {
        "intent": "detail", "metric": rank_metric,
        "dimensions": [f"{TABLE}.{rank_metric}", f"{TABLE}.{show}"],
        "time": LAST_MONTH, "sort": {"by": "metric", "dir": direction}, "limit": limit,
    }


# ---------------------------------------------------------------- 1. the reported case


def test_delay_minutes_is_a_measure_and_a_metric(fleet):
    """Root cause 1: a whole-number column with many values used to be `text`."""
    semantic, _, _ = fleet
    column = semantic.tables[TABLE].columns["delay_minutes"]
    metrics = {m.name: m for m in semantic.metrics}

    # The shape that used to fall through to `text`: over 20 distinct values, yet
    # under 5% of the rows (so neither a category nor a "many values" measure).
    assert 20 < column.distinct and column.distinct / semantic.tables[TABLE].row_count < 0.05
    assert column.role == "measure"
    assert "delay_minutes" in metrics and metrics["delay_minutes"].additive
    assert metrics["delay_minutes"].expr == f'SUM("{TABLE}"."delay_minutes")'


def test_the_swapped_plan_is_refused_not_answered(fleet):
    """Root cause 3: the model's actual plan (weight as metric, delay as a grouping)."""
    semantic, _, _ = fleet
    swapped = {
        "intent": "ranking", "metric": "package_weight_kg", "dimensions": [f"{TABLE}.delay_minutes"],
        "time": LAST_MONTH, "sort": {"by": "metric", "dir": "desc"}, "limit": 10,
    }
    _, errors, _ = validate_plan(Plan.model_validate(swapped), semantic)

    assert len(errors) == 1 and errors[0].startswith("MEASURE_AS_DIMENSION")
    assert "delay_minutes" in errors[0] and "top or bottom N records" in errors[0]


def test_top_10_delay_by_weight_returns_the_highest_delays_with_their_weights(fleet):
    semantic, db, frame = fleet
    sql, result, plan, _ = _run(semantic, db, _top_records_plan())

    december = frame[frame["d"] >= "2024-12-01"].sort_values("delay_minutes", ascending=False, kind="stable").head(10)
    assert result["columns"] == ["delay_minutes", "package_weight_kg"]
    assert [r[0] for r in result["rows"]] == december["delay_minutes"].tolist()
    assert [r[1] for r in result["rows"]] == december["package_weight_kg"].tolist()
    assert result["row_count"] == 10

    # Ordered by the ranked column, not aggregated, and bounded to the anchored month.
    assert 'ORDER BY "shipments"."delay_minutes" DESC NULLS LAST' in sql
    assert "GROUP BY" not in sql and "SUM(" not in sql and "LIMIT 10" in sql
    assert '"dispatch_date" >= ?' in sql            # values are bound, never interpolated
    assert plan.metric == "delay_minutes" and plan.intent == "detail"


def test_the_pipeline_corrects_the_swap_with_one_replan(fleet, monkeypatch):
    """Model swaps on the first try; told why, it plans records and the answer is right."""
    semantic, _, frame = fleet
    calls = []
    swapped = Plan.model_validate({
        "intent": "ranking", "metric": "package_weight_kg", "dimensions": [f"{TABLE}.delay_minutes"],
        "time": LAST_MONTH, "sort": {"by": "metric", "dir": "desc"}, "limit": 10,
    })
    corrected = Plan.model_validate(_top_records_plan())

    def planner(**kwargs):
        calls.append(kwargs.get("validation_feedback"))
        return PlannerOutput(plan=corrected if kwargs.get("validation_feedback") else swapped)

    response = _ask_pipeline(semantic, monkeypatch, "Top 10 delay_minutes by Package weight kg (Last 1 month)", planner)

    assert len(calls) == 2 and calls[0] is None and "delay_minutes" in calls[1]
    assert response["status"] == "ok" and response["plan"]["intent"] == "detail"
    assert response["plan"]["metric"] == "delay_minutes"
    december = frame[frame["d"] >= "2024-12-01"].sort_values("delay_minutes", ascending=False, kind="stable").head(10)
    assert [r[0] for r in response["result"]["rows"]] == december["delay_minutes"].tolist()
    assert response["chart"]["type"] == "table"                 # records are not plotted as bars
    assert "segment" not in response["narrative"].lower()


def test_a_plan_that_stays_wrong_is_reported_never_charted(fleet, monkeypatch):
    semantic, _, _ = fleet
    swapped = Plan.model_validate({
        "intent": "ranking", "metric": "package_weight_kg", "dimensions": [f"{TABLE}.delay_minutes"],
        "time": LAST_MONTH, "limit": 10,
    })
    calls = []

    def planner(**kwargs):
        calls.append(1)
        return PlannerOutput(plan=swapped)

    response = _ask_pipeline(semantic, monkeypatch, "Top 10 delay_minutes by Package weight kg", planner)

    assert len(calls) == 2                                    # one retry, then it stops
    assert response["status"] == "error"
    assert response["chart"] is None and response["result"] is None and response["sql"] is None
    assert "numeric measure" in response["narrative"] and "delay_minutes" in response["narrative"]


def test_errors_no_plan_can_fix_are_not_retried(fleet, monkeypatch):
    semantic, _, _ = fleet
    calls = []

    def planner(**kwargs):
        calls.append(1)
        return PlannerOutput(plan=Plan(intent="kpi", metric="package_weight_kg"))

    no_dates = semantic.model_copy(deep=True)
    no_dates.time.primary_column = None
    for metric in no_dates.metrics:
        metric.time_column = None
    response = _ask_pipeline(no_dates, monkeypatch, "total weight", planner)

    assert len(calls) == 1 and response["status"] == "error"


# ------------------------------------------ 2. another top-N: different metric, dimension


def test_top_n_of_a_category_by_a_metric_still_ranks_the_groups(fleet):
    """'Top 3 carriers by package weight' - the existing grouped ranking, unchanged."""
    semantic, db, frame = fleet
    plan = {"intent": "ranking", "metric": "package_weight_kg", "dimensions": [f"{TABLE}.carrier_name"],
            "time": LAST_MONTH, "sort": {"by": "metric", "dir": "desc"}, "limit": 3}
    sql, result, _, _ = _run(semantic, db, plan)

    expected = frame[frame["d"] >= "2024-12-01"].groupby("carrier_name")["package_weight_kg"].sum().nlargest(3)
    assert [r[0] for r in result["rows"]] == expected.index.tolist()
    for row, value in zip(result["rows"], expected.tolist()):
        assert row[1] == pytest.approx(value)
    assert "GROUP BY 1" in sql and "SUM(" in sql


def test_bottom_n_records_by_a_different_metric(fleet):
    """Lowest shipping cost, showing the carrier: another metric, another dimension, ascending."""
    semantic, db, frame = fleet
    plan = {"intent": "detail", "metric": "shipping_cost_usd",
            "dimensions": [f"{TABLE}.shipping_cost_usd", f"{TABLE}.carrier_name"],
            "time": LAST_MONTH, "sort": {"by": "metric", "dir": "asc"}, "limit": 5}
    sql, result, _, _ = _run(semantic, db, plan)

    cheapest = frame[frame["d"] >= "2024-12-01"].sort_values("shipping_cost_usd", kind="stable").head(5)
    assert result["columns"] == ["shipping_cost_usd", "carrier_name"]
    assert [r[0] for r in result["rows"]] == cheapest["shipping_cost_usd"].tolist()
    assert [r[1] for r in result["rows"]] == cheapest["carrier_name"].tolist()
    assert "ASC NULLS LAST" in sql


# ------------------------------------------------ 3. ordinary queries are unchanged


def test_a_normal_aggregation_is_unchanged(fleet):
    semantic, db, frame = fleet
    _, total, _, _ = _run(semantic, db, {"intent": "kpi", "metric": "package_weight_kg"})
    assert total["rows"][0][0] == pytest.approx(frame["package_weight_kg"].sum())

    sql, by_hub, _, _ = _run(semantic, db, {"intent": "breakdown", "metric": "shipping_cost_usd",
                                            "dimensions": [f"{TABLE}.origin_hub"], "sort": {"by": "metric", "dir": "desc"}})
    expected = frame.groupby("origin_hub")["shipping_cost_usd"].sum().sort_values(ascending=False)
    assert [r[0] for r in by_hub["rows"]] == expected.index.tolist()
    assert "GROUP BY 1" in sql


def test_grouping_by_a_low_cardinality_number_is_still_allowed(fleet):
    """`stops` (1-6) is a category in disguise; only high-cardinality measures are refused."""
    semantic, db, frame = fleet
    _, result, _, _ = _run(semantic, db, {"intent": "breakdown", "metric": "package_weight_kg",
                                          "dimensions": [f"{TABLE}.stops"]})
    assert result["row_count"] == 6


def test_a_listing_without_a_sort_keeps_its_original_unordered_form(fleet):
    """Alerts and 'list the records' plans have no metric or sort and must compile as before."""
    semantic, db, _ = fleet
    sql, result, _, _ = _run(semantic, db, {"intent": "detail", "dimensions": [f"{TABLE}.origin_hub", f"{TABLE}.stops"], "limit": 5})

    assert "ORDER BY" not in sql and result["row_count"] == 5


# ------------------------------- 4. two valid columns must never swap roles


def test_metric_and_dimension_are_not_swapped(fleet):
    """Both delay_minutes and package_weight_kg are valid metrics. Whichever the
    plan names as the metric is what the rows are ordered by - never the other one."""
    semantic, db, frame = fleet
    december = frame[frame["d"] >= "2024-12-01"]

    _, by_delay, _, _ = _run(semantic, db, _top_records_plan("delay_minutes", "package_weight_kg"))
    _, by_weight, _, _ = _run(semantic, db, _top_records_plan("package_weight_kg", "delay_minutes"))

    assert by_delay["columns"] == ["delay_minutes", "package_weight_kg"]
    assert by_weight["columns"] == ["package_weight_kg", "delay_minutes"]
    assert [r[0] for r in by_delay["rows"]] == december.sort_values("delay_minutes", ascending=False, kind="stable").head(10)["delay_minutes"].tolist()
    assert [r[0] for r in by_weight["rows"]] == december.sort_values("package_weight_kg", ascending=False, kind="stable").head(10)["package_weight_kg"].tolist()
    assert by_delay["rows"] != by_weight["rows"]


def test_a_metric_that_is_not_one_column_says_records_are_unordered(fleet):
    semantic, _, _ = fleet
    semantic = semantic.model_copy(deep=True)
    semantic.metrics[0].expr = 'SUM("shipments"."package_weight_kg") / NULLIF(COUNT(*), 0)'   # a ratio
    plan = {"intent": "detail", "metric": semantic.metrics[0].name, "dimensions": [f"{TABLE}.origin_hub"],
            "sort": {"by": "metric", "dir": "desc"}, "limit": 5}
    _, errors, notes = validate_plan(Plan.model_validate(plan), semantic)

    assert errors == [] and any("Records are not ordered" in n for n in notes)


def test_an_ad_hoc_metric_on_a_missing_column_is_rejected(fleet):
    semantic, _, _ = fleet
    plan = {"intent": "detail", "metric": {"agg": "max", "column": f"{TABLE}.no_such_column"},
            "sort": {"by": "metric", "dir": "desc"}, "limit": 5}
    _, errors, _ = validate_plan(Plan.model_validate(plan), semantic)
    assert any(e.startswith("UNKNOWN_COLUMN") for e in errors)


def test_a_stale_dataset_where_delay_was_text_is_still_protected(fleet):
    """Datasets stored before the tagger fix keep role `text`; the guard reads the type."""
    semantic, _, _ = fleet
    stale = semantic.model_copy(deep=True)
    stale.tables[TABLE].columns["delay_minutes"].role = "text"
    plan = {"intent": "ranking", "metric": "package_weight_kg", "dimensions": [f"{TABLE}.delay_minutes"], "limit": 10}
    _, errors, _ = validate_plan(Plan.model_validate(plan), stale)
    assert any(e.startswith("MEASURE_AS_DIMENSION") for e in errors)


# ------------------------------------------------------------------- narration


def test_a_record_listing_is_never_narrated_as_segments():
    plan = Plan.model_validate(_top_records_plan())
    result = {"columns": ["delay_minutes", "package_weight_kg"], "rows": [[211, 12.5], [210, 3.1]], "row_count": 2}

    text = generate_templated_narrative(plan, result, "Last 1 month")
    assert "segment" not in text.lower() and "share" not in text.lower()
    assert "highest delay minutes" in text and "211" in text and "210" in text
    assert compute_derived_stats(plan, result) == {}     # no "top share" over records


def test_a_breakdown_is_still_narrated_as_before():
    plan = Plan.model_validate({"intent": "breakdown", "metric": "package_weight_kg", "dimensions": [f"{TABLE}.origin_hub"]})
    result = {"columns": ["origin_hub", "package_weight_kg"], "rows": [["Chicago", 60.0], ["Newark", 40.0]], "row_count": 2}
    assert "Chicago is the leading segment with 60.00 (60.0% of total package weight kg)" in generate_templated_narrative(plan, result, "All Time")


# ------------------------------------------------------------------------ helpers


def _ask_pipeline(semantic, monkeypatch, question, planner):
    pipeline._DEMO_QUERY_CACHE.clear()
    monkeypatch.setattr(pipeline, "plan_query", planner)
    # Templated narration only: the LLM narrator is not under test here.
    monkeypatch.setattr(pipeline, "narrate_result", lambda **kwargs: generate_templated_narrative(
        kwargs["plan"], kwargs["result"], kwargs["period_label"], kwargs.get("baseline_label"), kwargs.get("why_result")))
    return pipeline.run_ask_pipeline(create_session("ds_fleet"), semantic, question, None)
