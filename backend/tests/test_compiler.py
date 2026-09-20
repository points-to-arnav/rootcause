import os
import pytest
from app.semantic.store import load_semantic_layer
from app.planner.plan_schema import Plan, Filter, TimeSpec, LastN
from app.planner.compiler import compile_plan_to_sql
from app.planner.executor import execute_query
from app.config import settings

def test_sql_compiler_kpi_and_breakdown():
    ds_id = "ds_retail_sample"
    semantic = load_semantic_layer(ds_id)
    if not semantic:
        pytest.skip("ds_retail_sample not available")

    db_path = os.path.join(settings.DATA_DIR, ds_id, "data.duckdb")

    # 1. Total revenue KPI
    target_window = ("2025-01-01", "2026-08-31")
    plan_kpi = Plan(intent="kpi", metric="revenue")
    sql, params = compile_plan_to_sql(plan_kpi, semantic, target_window=target_window)
    res = execute_query(db_path, sql, params)
    assert len(res["rows"]) == 1
    rev = res["rows"][0][0]
    assert rev > 1000000

    # 2. Revenue by region with join
    plan_brk = Plan(intent="breakdown", metric="revenue", dimensions=["customers.region"])
    sql2, params2 = compile_plan_to_sql(plan_brk, semantic, target_window=target_window)
    res2 = execute_query(db_path, sql2, params2)
    assert len(res2["rows"]) >= 4
