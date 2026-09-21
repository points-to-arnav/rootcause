"""
A dataset that is not retail-shaped (no sales/revenue/order_date) must still work.

These run the real ingestion, semantic layer, validator, compiler and executor - no
LLM - and compare the results with independent pandas calculations.
"""
import os

import pandas as pd
import pytest

from app.api.routes_datasets import process_and_save_dataset
from app.config import settings
from app.planner.compiler import compile_plan_to_sql
from app.planner.executor import execute_query
from app.planner.plan_schema import Plan, TimeSpec
from app.planner.timeutil import resolve_time_window
from app.planner.validator import validate_plan

TABLE = "service_metrics"


def _frame() -> pd.DataFrame:
    dates = pd.date_range("2025-01-01", periods=90, freq="D")
    rows = []
    for i, day in enumerate(dates):
        for service in ("api", "auth", "search"):
            rows.append({
                "metric_id": f"M-{len(rows):05d}",
                "recorded_date": day.strftime("%Y-%m-%d"),
                "service_name": service,
                "cloud_region": "us-east" if i % 2 else "eu-west",
                "request_count": 1000 + i * 7 + len(service) * 13,
                "p99_latency_ms": round(40 + (i % 9) * 3.7 + len(service), 2),
                # Few distinct values: the case the old tagger called "text".
                "error_rate_pct": [0.1, 0.2, 0.3, 0.4][i % 4],
                "cloud_spend_usd": round(100 + i * 1.5 + len(service) * 9.25, 2),
            })
    return pd.DataFrame(rows)


@pytest.fixture()
def dataset(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "DATA_DIR", str(tmp_path))
    frame = _frame()
    csv = tmp_path / f"{TABLE}.csv"
    frame.to_csv(csv, index=False)
    semantic = process_and_save_dataset("ds_generic", [str(csv)])
    frame["d"] = pd.to_datetime(frame["recorded_date"])
    return semantic, os.path.join(str(tmp_path), "ds_generic", "data.duckdb"), frame


def _run(semantic, db_path, plan: Plan):
    plan, errors, _ = validate_plan(plan, semantic)
    assert errors == []
    start, end, _ = resolve_time_window(
        plan.time.range if plan.time else None,
        anchor_str=semantic.time.anchor_date,
        min_date_str=semantic.time.min,
    )
    sql, params = compile_plan_to_sql(plan, semantic, (start, end))
    return sql, execute_query(db_path, sql, params)


def test_low_cardinality_double_is_a_measure_not_text(dataset):
    semantic, _, _ = dataset
    roles = {c: m.role for c, m in semantic.tables[TABLE].columns.items()}

    assert roles["error_rate_pct"] == "measure"
    assert roles["recorded_date"] == "time"
    assert roles["service_name"] == "dimension"


def test_metrics_are_derived_from_the_columns_and_rates_are_averaged(dataset):
    semantic, _, _ = dataset
    metrics = {m.name: m for m in semantic.metrics}

    assert {"request_count", "cloud_spend_usd", "p99_latency_ms", "error_rate_pct", "records"} <= set(metrics)
    assert metrics["cloud_spend_usd"].expr.startswith("SUM(") and metrics["cloud_spend_usd"].additive
    assert metrics["cloud_spend_usd"].format == "currency"
    # A rate summed across rows is meaningless, so it is averaged and non-additive.
    assert metrics["error_rate_pct"].expr.startswith("AVG(") and not metrics["error_rate_pct"].additive
    assert metrics["error_rate_pct"].format == "percent"
    assert metrics["p99_latency_ms"].expr.startswith("AVG(")


def test_total_matches_pandas_and_never_mentions_a_sales_table(dataset):
    semantic, db, frame = dataset
    sql, result = _run(semantic, db, Plan(intent="kpi", metric="cloud_spend_usd"))

    assert "sales" not in sql.lower() and "order_date" not in sql.lower()
    assert result["rows"][0][0] == pytest.approx(frame["cloud_spend_usd"].sum())


def test_breakdown_by_dimension_matches_pandas(dataset):
    semantic, db, frame = dataset
    plan = Plan(intent="breakdown", metric="request_count", dimensions=[f"{TABLE}.service_name"])
    _, result = _run(semantic, db, plan)

    expected = frame.groupby("service_name")["request_count"].sum()
    actual = {row[0]: row[1] for row in result["rows"]}
    assert set(actual) == set(expected.index)
    for service, value in expected.items():
        assert actual[service] == pytest.approx(value)


def test_average_metric_is_averaged_not_summed(dataset):
    semantic, db, frame = dataset
    plan = Plan(intent="breakdown", metric="p99_latency_ms", dimensions=[f"{TABLE}.cloud_region"])
    _, result = _run(semantic, db, plan)

    expected = frame.groupby("cloud_region")["p99_latency_ms"].mean()
    for region, value in {row[0]: row[1] for row in result["rows"]}.items():
        assert value == pytest.approx(expected[region])


def test_monthly_trend_matches_pandas(dataset):
    semantic, db, frame = dataset
    _, result = _run(semantic, db, Plan(intent="trend", metric="cloud_spend_usd", time=TimeSpec(grain="month")))

    expected = frame.groupby(frame["d"].dt.to_period("M"))["cloud_spend_usd"].sum()
    actual = {str(row[0])[:7]: row[1] for row in result["rows"]}
    assert len(actual) == len(expected)
    for month, value in expected.items():
        assert actual[str(month)] == pytest.approx(value)


def test_missing_metric_defaults_to_one_the_dataset_has(dataset):
    semantic, _, _ = dataset
    plan, errors, assumptions = validate_plan(Plan(intent="kpi", metric=None), semantic)

    assert errors == []
    assert plan.metric == semantic.metrics[0].name
    assert any("Defaulted" in a for a in assumptions)


def test_unknown_metric_error_lists_what_is_available(dataset):
    semantic, _, _ = dataset
    _, errors, _ = validate_plan(Plan(intent="kpi", metric="revenue"), semantic)

    assert errors and "UNKNOWN_METRIC" in errors[0]
    assert "cloud_spend_usd" in errors[0]


def test_why_on_an_average_is_refused_not_answered_wrongly(dataset):
    semantic, _, _ = dataset
    _, errors, _ = validate_plan(Plan(intent="why", metric="error_rate_pct"), semantic)

    assert any("NON_ADDITIVE_WHY" in e for e in errors)


def test_dataset_without_a_date_column_fails_visibly(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "DATA_DIR", str(tmp_path))
    csv = tmp_path / "no_dates.csv"
    pd.DataFrame({"team": ["a", "b", "c", "a"] * 10, "tickets": [1 + i % 7 for i in range(40)]}).to_csv(csv, index=False)
    semantic = process_and_save_dataset("ds_nodate", [str(csv)])

    _, errors, _ = validate_plan(Plan(intent="kpi", metric="tickets"), semantic)
    assert any("NO_TIME_COLUMN" in e for e in errors)


def test_retail_shaped_data_still_gets_the_domain_metrics(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "DATA_DIR", str(tmp_path))
    csv = tmp_path / "sales.csv"
    pd.DataFrame({
        "order_id": [f"O{i}" for i in range(40)],
        "order_date": pd.date_range("2025-01-01", periods=40).strftime("%Y-%m-%d"),
        "quantity": [1 + i % 4 for i in range(40)],
        "amount": [10.0 + i for i in range(40)],
    }).to_csv(csv, index=False)
    semantic = process_and_save_dataset("ds_retailish", [str(csv)])
    names = [m.name for m in semantic.metrics]

    assert names[:3] == ["revenue", "units", "orders"]
    assert "records" not in names  # generic metrics are only for data the rules don't recognise
