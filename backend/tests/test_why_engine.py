import os
import datetime
import pytest
from app.semantic.store import load_semantic_layer
from app.analysis.why_engine import run_why_analysis
from app.config import settings

def test_why_engine_august_drop():
    ds_id = "ds_retail_sample"
    semantic = load_semantic_layer(ds_id)
    if not semantic:
        pytest.skip("ds_retail_sample not available")

    db_path = os.path.join(settings.DATA_DIR, ds_id, "data.duckdb")

    # August 2026 vs July 2026
    target_window = (datetime.date(2026, 8, 1), datetime.date(2026, 8, 31))
    baseline_window = (datetime.date(2026, 7, 1), datetime.date(2026, 7, 31))

    why_res = run_why_analysis(
        db_path=db_path,
        semantic=semantic,
        metric_name="revenue",
        target_window=target_window,
        baseline_window=baseline_window,
        candidate_dims=["products.category", "customers.region"]
    )

    assert why_res["direction"] == "decrease"
    assert why_res["delta"] < 0
    # Invariant: segments sum to delta
    for dim_res in why_res["dimensions"]:
        seg_delta_sum = sum(s["delta"] for s in dim_res["segments"])
        assert abs(seg_delta_sum - why_res["delta"]) < 0.1

    # Top driver segment
    top_dim = why_res["dimensions"][0]
    top_seg = top_dim["segments"][0]
    assert top_seg["contribution"] >= 0.30
