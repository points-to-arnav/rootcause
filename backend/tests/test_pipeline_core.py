import os
import pytest
from app.api.routes_datasets import process_and_save_dataset
from app.semantic.store import load_semantic_layer
from app.config import settings

def test_ingestion_and_semantic_pipeline():
    sample_file = "/home/sahajdeep/Desktop/rootcause/sample_data/retail_demo.xlsx"
    if not os.path.exists(sample_file):
        pytest.skip("retail_demo.xlsx not generated yet")

    test_ds_id = "test_ds_core"
    semantic = process_and_save_dataset(test_ds_id, [sample_file])

    assert semantic.dataset_id == test_ds_id
    assert len(semantic.tables) >= 4
    assert "sales" in semantic.tables
    assert "customers" in semantic.tables
    assert semantic.fact_table == "sales"
    assert semantic.time.anchor_date == "2026-08-31"

    # Relationships
    assert len(semantic.relationships) >= 2
    rel_pairs = [(r.from_col, r.to_col) for r in semantic.relationships]
    assert any("customer_id" in p[0] and "customer_id" in p[1] for p in rel_pairs)

    # Metrics
    metric_names = [m.name for m in semantic.metrics]
    assert "revenue" in metric_names

    # Data Quality
    assert len(semantic.quality_issues) > 0
    issue_types = {i["type"] for i in semantic.quality_issues}
    assert any(t in issue_types for t in ["missing_values", "negative_values", "duplicate_rows", "outliers"])

    # Test persistence load
    loaded = load_semantic_layer(test_ds_id)
    assert loaded is not None
    assert loaded.fact_table == "sales"
