from typing import Any, Dict, List
from app.semantic.model import Metric, TableMeta

def register_metrics(tables: Dict[str, TableMeta], fact_table: str) -> List[Metric]:
    """
    Auto-detects and registers standard business metrics across fact and related tables.
    """
    metrics: List[Metric] = []
    fact_meta = tables.get(fact_table)
    if not fact_meta:
        return metrics

    # Find fact time column
    fact_time_col = None
    for cname, cmeta in fact_meta.columns.items():
        if cmeta.role == "time":
            fact_time_col = f"{fact_table}.{cname}"
            break

    # 1. Revenue
    rev_cols = ["amount", "revenue", "sales", "net_sales", "total", "line_total"]
    found_rev = None
    for rc in rev_cols:
        if rc in fact_meta.columns:
            found_rev = rc
            break

    if found_rev:
        metrics.append(Metric(
            name="revenue",
            label="Revenue",
            table=fact_table,
            expr=f'SUM("{fact_table}"."{found_rev}")',
            additive=True,
            format="currency",
            time_behavior="flow",
            time_column=fact_time_col,
            synonyms=["sales", "turnover", "income", "total sales", "revnue"],
            description="Total net revenue after discount"
        ))

    # 2. Units / Quantity
    qty_cols = ["quantity", "qty", "units"]
    found_qty = None
    for qc in qty_cols:
        if qc in fact_meta.columns:
            found_qty = qc
            break

    if found_qty:
        metrics.append(Metric(
            name="units",
            label="Units Sold",
            table=fact_table,
            expr=f'SUM("{fact_table}"."{found_qty}")',
            additive=True,
            format="count",
            time_behavior="flow",
            time_column=fact_time_col,
            synonyms=["quantity", "volume", "items sold"],
            description="Total quantity of products sold"
        ))

    # 3. Orders / Order Count
    order_id_col = None
    for cname in ["order_id", "id", "order_number"]:
        if cname in fact_meta.columns:
            order_id_col = cname
            break

    if order_id_col:
        metrics.append(Metric(
            name="orders",
            label="Orders",
            table=fact_table,
            expr=f'COUNT(DISTINCT "{fact_table}"."{order_id_col}")',
            additive=True,
            format="count",
            time_behavior="flow",
            time_column=fact_time_col,
            synonyms=["transactions", "order count", "number of orders"],
            description="Total distinct orders placed"
        ))

    # 4. Average Order Value (AOV)
    if found_rev and order_id_col:
        metrics.append(Metric(
            name="avg_order_value",
            label="Average Order Value",
            table=fact_table,
            expr=f'SUM("{fact_table}"."{found_rev}") / NULLIF(COUNT(DISTINCT "{fact_table}"."{order_id_col}"), 0)',
            expr_conditional=(
                f'SUM("{fact_table}"."{found_rev}") FILTER (WHERE {{cond}}) / '
                f'NULLIF(COUNT(DISTINCT "{fact_table}"."{order_id_col}") FILTER (WHERE {{cond}}), 0)'
            ),
            additive=False,  # Ratio metric!
            format="currency",
            time_behavior="flow",
            time_column=fact_time_col,
            synonyms=["aov", "average basket", "ticket size"],
            description="Average revenue generated per order"
        ))

    # 5. Returns / Refunds (if returns table exists)
    if "returns" in tables:
        ret_meta = tables["returns"]
        ref_col = None
        for c in ["refund_amount", "amount", "refund"]:
            if c in ret_meta.columns:
                ref_col = c
                break
        if ref_col:
            metrics.append(Metric(
                name="refunds",
                label="Refunds",
                table="returns",
                expr=f'SUM("returns"."{ref_col}")',
                additive=True,
                format="currency",
                time_behavior="flow",
                time_column="returns.return_date" if "return_date" in ret_meta.columns else None,
                synonyms=["returns amount", "refund total"],
                description="Total refunds issued on returns"
            ))

    # 6. Return Rate (cross-fact semi-join)
    if "returns" in tables and order_id_col and "order_id" in tables["returns"].columns:
        metrics.append(Metric(
            name="return_rate",
            label="Return Rate",
            table=fact_table,
            expr=f'COUNT(DISTINCT CASE WHEN ret."order_id" IS NOT NULL THEN "{fact_table}"."{order_id_col}" END) * 100.0 / NULLIF(COUNT(DISTINCT "{fact_table}"."{order_id_col}"), 0)',
            expr_conditional=(
                f'COUNT(DISTINCT CASE WHEN ret."order_id" IS NOT NULL '
                f'THEN "{fact_table}"."{order_id_col}" END) FILTER (WHERE {{cond}}) * 100.0 / '
                f'NULLIF(COUNT(DISTINCT "{fact_table}"."{order_id_col}") FILTER (WHERE {{cond}}), 0)'
            ),
            additive=False,
            format="percent",
            time_behavior="flow",
            time_column=fact_time_col,
            extra_joins=[{
                "table": "returns",
                "alias": "ret",
                "on": f'"{fact_table}"."{order_id_col}" = ret."order_id"',
                "mode": "distinct_semijoin"
            }],
            synonyms=["return percentage", "order return rate"],
            description="Percentage of total orders that resulted in a return"
        ))

    # 7. Inventory Stock on Hand (snapshot metric)
    if "inventory" in tables and "stock_on_hand" in tables["inventory"].columns:
        metrics.append(Metric(
            name="stock_on_hand",
            label="Stock on Hand",
            table="inventory",
            expr='SUM("inventory"."stock_on_hand")',
            additive=False,  # Snapshot metric! Non-additive across time
            format="count",
            time_behavior="snapshot",
            time_column="inventory.snapshot_date" if "snapshot_date" in tables["inventory"].columns else None,
            synonyms=["inventory", "stock", "available units"],
            description="Snapshot of available warehouse stock level"
        ))

    return metrics
