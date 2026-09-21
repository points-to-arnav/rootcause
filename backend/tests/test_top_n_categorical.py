"""
"Top N <categorical column> by <numeric metric>" ranks the categories by SUM(metric).

Reported as a bug: "Top 10 delivery_status by Package weight kg (Last 1 month)" drew a
single bar, "Delivered On Time". That answer is correct: in the last month of that data
every shipment is on time - the other statuses only occur in the November storms. These
tests pin the interpretation (a SUM of the metric per category, never a row count) and
its contrast with a numeric column, which is ranked as individual records instead
(see test_top_n_planning.py).

Real ingestion, validator, compiler and pipeline; the planner is stubbed (no LLM); every
figure is checked against an independent pandas calculation.
"""
import os

import pandas as pd
import pytest

import app.pipeline as pipeline
from app.api.routes_datasets import process_and_save_dataset
from app.config import settings
from app.memory.session import create_session
from app.narrator.narrator import generate_templated_narrative
from app.planner.compiler import compile_plan_to_sql
from app.planner.executor import execute_query
from app.planner.plan_schema import Plan, PlannerOutput
from app.planner.timeutil import resolve_time_window
from app.planner.validator import validate_plan

TABLE = "shipments"
STATUSES = ["Delivered On Time", "Rerouted", "Delayed - Ground Stop", "Delayed - Severe Weather"]

LAST_MONTH = {"range": {"type": "last_n", "unit": "month", "n": 1}}
LAST_TWO_MONTHS = {"range": {"type": "last_n", "unit": "month", "n": 2}}
WINDOWS = {  # name -> (time spec, first day of the window)
    "last month": (LAST_MONTH, "2024-12-01"),
    "last two months": (LAST_TWO_MONTHS, "2024-11-01"),
    "all time": (None, "2000-01-01"),
}


def _frame() -> pd.DataFrame:
    days = pd.date_range("2024-11-01", "2024-12-31", freq="D")
    rows = []
    for i in range(2400):
        day = days[i % len(days)]
        # Disruptions exist only in November, like a storm month in real data.
        status = STATUSES[1 + i % 3] if (day.month == 11 and i % 10 < 3) else STATUSES[0]
        rows.append({
            "shipment_id": f"SHIP-{i:05d}",
            "dispatch_date": day.strftime("%Y-%m-%d"),
            "origin_hub": ["Chicago", "Newark", "Dallas", "Denver", "Miami"][i % 5],
            "carrier_name": ["UPS", "FedEx", "DHL", "OnTrac"][(i * 3) % 4],
            "package_weight_kg": round(1 + (i * 7919 % 4000) / 100, 2),
            "delay_minutes": (i * 37) % 95,          # ~95 distinct whole numbers
            "delivery_status": status,
        })
    return pd.DataFrame(rows)


@pytest.fixture()
def data(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "DATA_DIR", str(tmp_path))
    frame = _frame()
    csv = tmp_path / f"{TABLE}.csv"
    frame.to_csv(csv, index=False)
    semantic = process_and_save_dataset("ds_status", [str(csv)])
    frame["d"] = pd.to_datetime(frame["dispatch_date"])
    return semantic, os.path.join(str(tmp_path), "ds_status", "data.duckdb"), frame


def _run(semantic, db_path, plan_dict):
    plan, errors, notes = validate_plan(Plan.model_validate(plan_dict), semantic)
    assert errors == [], errors
    start, end, _ = resolve_time_window(
        plan.time.range if plan.time else None, semantic.time.anchor_date, semantic.time.min
    )
    sql, params = compile_plan_to_sql(plan, semantic, (start, end))
    return " ".join(sql.split()), execute_query(db_path, sql, params), plan


def _rank(dimension, metric="package_weight_kg", time=LAST_MONTH, limit=10):
    plan = {"intent": "ranking", "metric": metric, "dimensions": [f"{TABLE}.{dimension}"],
            "sort": {"by": "metric", "dir": "desc"}, "limit": limit}
    if time is not None:
        plan["time"] = time
    return plan


def _top_records(rank_column, show_column, limit=10):
    return {"intent": "detail", "metric": rank_column,
            "dimensions": [f"{TABLE}.{rank_column}", f"{TABLE}.{show_column}"],
            "time": LAST_MONTH, "sort": {"by": "metric", "dir": "desc"}, "limit": limit}


# ------------------------------------------------ categorical column, numeric metric


@pytest.mark.parametrize("window", WINDOWS)
def test_categories_are_ranked_by_the_sum_of_the_metric(data, window):
    semantic, db, frame = data
    time, since = WINDOWS[window]
    sql, result, plan = _run(semantic, db, _rank("delivery_status", time=time))

    scope = frame[frame["d"] >= since]
    expected = scope.groupby("delivery_status")["package_weight_kg"].sum().sort_values(ascending=False)
    counts = scope["delivery_status"].value_counts().reindex(expected.index)

    assert result["columns"] == ["delivery_status", "package_weight_kg"]
    assert [r[0] for r in result["rows"]] == expected.index.tolist()
    assert [r[1] for r in result["rows"]] == pytest.approx(expected.tolist())
    # A weight total, not a record count.
    assert all(row[1] != count for row, count in zip(result["rows"], counts))
    assert 'SUM("shipments"."package_weight_kg")' in sql and "GROUP BY 1" in sql
    assert 'ORDER BY "package_weight_kg" DESC' in sql and "LIMIT 10" in sql
    assert plan.intent == "ranking" and plan.metric == "package_weight_kg"


def test_a_month_with_one_category_gives_one_ranked_row_and_is_not_a_bug(data):
    """The reported case: only one status exists in the anchored month."""
    semantic, db, frame = data
    _, result, _ = _run(semantic, db, _rank("delivery_status"))

    december = frame[frame["d"] >= "2024-12-01"]
    assert december["delivery_status"].nunique() == 1
    assert result["row_count"] == 1
    assert result["rows"][0][0] == STATUSES[0]
    assert result["rows"][0][1] == pytest.approx(december["package_weight_kg"].sum())


def test_the_disrupted_categories_appear_once_the_window_includes_them(data):
    semantic, db, _ = data
    _, result, _ = _run(semantic, db, _rank("delivery_status", time=LAST_TWO_MONTHS))
    assert {r[0] for r in result["rows"]} == set(STATUSES)


@pytest.mark.parametrize("dimension", ["origin_hub", "carrier_name", "delivery_status"])
def test_any_categorical_column_is_ranked_the_same_way(data, dimension):
    """The rule is about the column's kind, not about one column name."""
    semantic, db, frame = data
    assert semantic.tables[TABLE].columns[dimension].role == "dimension"
    sql, result, _ = _run(semantic, db, _rank(dimension, time=None))

    expected = frame.groupby(dimension)["package_weight_kg"].sum().sort_values(ascending=False)
    assert [r[0] for r in result["rows"]] == expected.index.tolist()
    assert [r[1] for r in result["rows"]] == pytest.approx(expected.tolist())
    assert f'"{dimension}"' in sql and "GROUP BY 1" in sql


def test_a_numeric_measure_with_no_named_metric_column_is_summed_per_category(data):
    """Top carriers by delay minutes: delay_minutes is a metric, summed per carrier."""
    semantic, db, frame = data
    sql, result, _ = _run(semantic, db, _rank("carrier_name", metric="delay_minutes", time=None))

    expected = frame.groupby("carrier_name")["delay_minutes"].sum().sort_values(ascending=False)
    assert [r[0] for r in result["rows"]] == expected.index.tolist()
    assert [r[1] for r in result["rows"]] == pytest.approx(expected.tolist())
    assert 'SUM("shipments"."delay_minutes")' in sql


def test_ranking_by_the_row_count_metric_still_counts(data):
    semantic, db, frame = data
    _, result, _ = _run(semantic, db, _rank("delivery_status", metric="records", time=None))
    assert {r[0]: r[1] for r in result["rows"]} == frame["delivery_status"].value_counts().to_dict()


# ------------------------------------ numeric column: the contrast, and the general rule


def test_the_same_sentence_shape_reads_differently_by_column_kind(data):
    """'Top 10 <X> by package weight': X a category -> group and sum; X a number -> records."""
    semantic, db, frame = data
    columns = semantic.tables[TABLE].columns

    # X = delivery_status (a category): a grouping, ranked by SUM(weight).
    assert columns["delivery_status"].role == "dimension"
    sql_cat, cat, _ = _run(semantic, db, _rank("delivery_status", time=None))
    assert "GROUP BY 1" in sql_cat and cat["row_count"] == len(STATUSES)

    # X = delay_minutes (a number): refused as a grouping ...
    assert columns["delay_minutes"].role == "measure" and columns["delay_minutes"].distinct > 50
    _, errors, _ = validate_plan(Plan.model_validate(_rank("delay_minutes", time=None)), semantic)
    assert len(errors) == 1 and errors[0].startswith("MEASURE_AS_DIMENSION")

    # ... and answered as the individual records with the highest delay.
    sql_num, num, _ = _run(semantic, db, _top_records("delay_minutes", "package_weight_kg"))
    december = frame[frame["d"] >= "2024-12-01"].sort_values("delay_minutes", ascending=False, kind="stable").head(10)
    assert "GROUP BY" not in sql_num and 'ORDER BY "shipments"."delay_minutes" DESC' in sql_num
    assert [r[0] for r in num["rows"]] == december["delay_minutes"].tolist()
    assert [r[1] for r in num["rows"]] == december["package_weight_kg"].tolist()


def test_the_grouping_rule_follows_the_column_kind_for_every_column(data):
    """Generic: a category is always groupable; a high-cardinality number never is."""
    semantic, _, _ = data
    checked = 0
    for name, column in semantic.tables[TABLE].columns.items():
        if column.role not in ("dimension", "measure"):
            continue
        _, errors, _ = validate_plan(Plan.model_validate(_rank(name, time=None)), semantic)
        refused = any(e.startswith("MEASURE_AS_DIMENSION") for e in errors)
        should_refuse = column.role == "measure" and column.dtype in ("BIGINT", "DOUBLE") and column.distinct > 50
        assert refused == should_refuse, f"{name}: role={column.role} distinct={column.distinct} errors={errors}"
        checked += 1
    assert checked >= 4


# ------------------------------------------------------------------------ pipeline


def _ask(semantic, monkeypatch, question, planner):
    pipeline._DEMO_QUERY_CACHE.clear()
    monkeypatch.setattr(pipeline, "plan_query", planner)
    monkeypatch.setattr(pipeline, "narrate_result", lambda **kwargs: generate_templated_narrative(
        kwargs["plan"], kwargs["result"], kwargs["period_label"], kwargs.get("baseline_label"), kwargs.get("why_result")))
    return pipeline.run_ask_pipeline(create_session("ds_status"), semantic, question, None)


def test_the_reported_question_needs_no_replan_and_draws_the_ranked_categories(data, monkeypatch):
    """Through the pipeline with the plan the LLM really returned: one planner call, bars."""
    semantic, _, frame = data
    calls = []

    def planner(**kwargs):
        calls.append(kwargs.get("validation_feedback"))
        return PlannerOutput(plan=Plan.model_validate(_rank("delivery_status", time=LAST_TWO_MONTHS)))

    response = _ask(semantic, monkeypatch, "Top 10 delivery_status by Package weight kg (Last 2 months)", planner)

    assert calls == [None]                                   # accepted first time: no correction needed
    assert response["status"] == "ok" and response["chart"]["type"] in ("bar", "bar_h")
    expected = frame[frame["d"] >= "2024-11-01"].groupby("delivery_status")["package_weight_kg"].sum().sort_values(ascending=False)
    assert [r[0] for r in response["result"]["rows"]] == expected.index.tolist()
    assert [r[1] for r in response["result"]["rows"]] == pytest.approx(expected.tolist())
