from datetime import date
from typing import Any, Dict, List, Optional
import duckdb
from app.config import settings
from app.semantic.model import SemanticLayer

def generate_alerts(
    db_path: str,
    semantic: SemanticLayer,
    kpis: List[Dict[str, Any]],
    current_period: str
) -> List[Dict[str, Any]]:
    """
    Evaluates business alerts:
    1. KPI Drop (>10% drop vs previous period) -> links to Why plan!
    2. Low stock (stock_on_hand <= reorder_level)
    3. High-severity data quality issues
    """
    alerts = []

    # 1. KPI Drop Alerts
    for kpi in kpis:
        dp = kpi.get("delta_pct")
        metric = kpi.get("metric", "revenue")
        if dp is not None and dp <= -settings.ALERT_DROP_PCT:
            alerts.append({
                "id": f"alert_drop_{metric}",
                "severity": "high" if dp <= -20.0 else "medium",
                "type": "kpi_drop",
                "title": f"Significant Drop in {kpi.get('label', metric)}",
                "detail": f"{kpi.get('label', metric)} fell {abs(dp)}% ({kpi.get('delta', 0):,.2f}) in {current_period} compared to previous month.",
                "plan": {
                    "intent": "why",
                    "metric": metric,
                    "time": {"range": {"type": "last_n", "unit": "month", "n": 1}},
                    "comparison": {"type": "previous_period"}
                }
            })

    # 2. Low Stock Alerts (defensively check table and required columns)
    if "inventory" in semantic.tables:
        inv_meta = semantic.tables["inventory"]
        has_stock = "stock_on_hand" in inv_meta.columns
        has_reorder = "reorder_level" in inv_meta.columns
        has_date = "snapshot_date" in inv_meta.columns

        if has_stock and has_reorder and has_date:
            try:
                con = duckdb.connect(db_path, read_only=True)
                low_stock_rows = con.execute('''
                    SELECT COUNT(*), COUNT(CASE WHEN "stock_on_hand" = 0 THEN 1 END)
                    FROM "inventory"
                    WHERE "snapshot_date" = (SELECT MAX("snapshot_date") FROM "inventory")
                      AND "stock_on_hand" <= "reorder_level"
                ''').fetchone()
                con.close()

                total_low = low_stock_rows[0]
                out_of_stock = low_stock_rows[1]

                if total_low > 0:
                    alerts.append({
                        "id": "alert_low_stock",
                        "severity": "high" if out_of_stock > 0 else "medium",
                        "type": "low_stock",
                        "title": "Inventory Stockout / Low Stock Alert",
                        "detail": f"{total_low} product-region entries are at or below reorder levels ({out_of_stock} completely out of stock).",
                        "plan": {
                            "intent": "detail",
                            "dimensions": ["inventory.product_id", "inventory.warehouse_region", "inventory.stock_on_hand", "inventory.reorder_level"],
                            "filters": [{"column": "inventory.stock_on_hand", "op": "<=", "value": 0}]
                        }
                    })
            except Exception:
                pass

    # 3. High-Severity Data Quality Alerts
    for dq in semantic.quality_issues:
        if dq.get("severity") == "high":
            alerts.append({
                "id": f"alert_{dq['id']}",
                "severity": "high",
                "type": "data_quality",
                "title": f"Data Quality Warning: {dq.get('type', 'Issue').replace('_', ' ').title()}",
                "detail": dq.get("message", "") + " " + dq.get("impact", "")
            })

    return alerts
