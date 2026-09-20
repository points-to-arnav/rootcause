# semantic-layer.md: Roles, Relationships, Metrics, Value Index

The semantic layer is the schema-aware knowledge the planner and validator rely on. It is built deterministically from the profiled data; LLM enrichment is optional and never changes structure.

Where this file is more detailed than `architecture.md` section 4, this file wins. Refinements introduced here: column flag `entity`; metric fields `time_behavior` and `extra_joins`; `label` and `source` fields.

## 1. Precedence
User edits (P1) > LLM enrichment > automatic detection. Enrichment can set descriptions, synonyms and metric suggestions only; it cannot change dtype, role, relationships or SQL expressions.

## 2. Full JSON shape
```json
{
  "dataset_id": "ds_ab12cd34",
  "tables": {
    "sales": {
      "display_name": "Sales", "row_count": 18000, "role": "fact",
      "columns": {
        "amount": {
          "display_name": "Amount", "dtype": "DOUBLE", "role": "measure",
          "entity": false, "description": "Order value after discount",
          "null_pct": 0.0, "distinct": 9421, "min": 5.0, "max": 98000.0,
          "samples": [120.5, 999.0], "source": "auto"
        }
      }
    }
  },
  "relationships": [
    {"from": "sales.customer_id", "to": "customers.customer_id",
     "type": "many_to_one", "confidence": 0.97, "containment": 0.999,
     "parent_unique": true, "confirmed": false}
  ],
  "metrics": [
    {"name": "revenue", "label": "Revenue", "table": "sales",
     "expr": "SUM(sales.amount)", "additive": true, "format": "currency",
     "time_behavior": "flow", "time_column": "sales.order_date",
     "extra_joins": [], "synonyms": ["sales", "turnover", "income"],
     "description": "Total order value", "source": "auto"}
  ],
  "time": {"primary_column": "sales.order_date", "min": "2025-01-01",
           "max": "2026-08-31", "anchor_date": "2026-08-31"},
  "quality_issues": []
}
```
`source` is `auto`, `enriched` or `user`. Roles: `id`, `time`, `measure`, `dimension`, `text`.

## 3. Column role tagging (`semantic/tagger.py`)
Evaluate rules in this order; the first match wins.

1. **time:** dtype is DATE or TIMESTAMP.
2. **id:** name matches `(^|_)(id|key|code|no|number)$` (or equals `id`) **and** distinct ratio ≥ 0.5; or the column is unique across a table with more than 1 row and its dtype is integer or text.
3. **measure:** numeric dtype (BIGINT/DOUBLE), not id, and either distinct ratio > 0.05 or the name matches `amount|price|cost|revenue|sales|total|qty|quantity|units|stock|discount|profit|margin|balance|value|fee|tax|refund`.
4. **dimension:** VARCHAR or BOOLEAN with distinct ≤ max(50, 5% of rows); or numeric with distinct ≤ 20 that did not match measure rules (e.g. year, rating).
5. **text:** everything else (high-cardinality VARCHAR).

**Entity flag:** a `text` column is `entity: true` when its distinct ratio within its table is ≥ 0.9 and its name does not match `comment|description|notes?|remarks?|address|url|email|phone`. Entity columns are usable as the dimension for rankings ("top 10 customers" → `customers.customer_name`). If entity names are not unique, groups with the same name are merged; this is a known limitation.

**Group-by eligibility** (used by the validator): roles `dimension`; `text` with `entity: true`; `id` only for `ranking`; never `measure`, `time` (use `time.grain`).

## 4. Relationship detection (`semantic/relationships.py`)
For every ordered pair (child column C, parent column P) in different tables:
1. **Candidates:** dtypes are compatible (both integer, both text, or integer vs text-that-looks-numeric is rejected) and names match: equal after normalising, or C is `<parent_table>_id` / `<parent_singular>_id` and P is `id`/`<...>_id`.
2. **Parent key test:** distinct ÷ non-null count of P ≥ 0.99.
3. **Containment:** share of C's distinct non-null values that exist in P ≥ 0.95.
4. **Confidence** = 0.4 × name_score (1.0 exact, 0.7 pattern) + 0.4 × containment + 0.2 × parent_uniqueness, rounded to 2 decimals.
5. **Type:** `many_to_one` (C → P). If both sides are unique it is `one_to_one`.
6. Keep the highest-confidence relationship per (child column, parent table). Discard pairs below confidence 0.7.

Orphan child values (in C, not in P) are recorded as an `orphan_keys` data-quality issue.

Known limitations: relationships between differently named keys (e.g. `o_custkey` vs `c_custkey`) and parents with non-unique keys (e.g. `returns.order_id` → an orders table with several lines per order) are not detected in P0.

## 5. Join graph and fact table
- **Graph:** nodes are tables; directed edges go from child to parent (many-to-one).
- **Reachability:** from a fact table, dimension tables are reached by following edges child → parent, shortest path first, up to 3 hops. A path may pass through another table (e.g. `returns → sales → customers`).
- **Fact table for the dataset:** the table with the most rows that is child in the most edges and contains a time column and at least one measure. It sets `time.primary_column`, `min`, `max` and `anchor_date` (= max of the primary time column, as a date).
- **Fact table for a plan:** the `table` of the plan's metric. Its default time column is the metric's `time_column`.

## 6. Metrics registry (`semantic/metrics.py`)
Generated for every fact-like table (a table that is child in at least one edge, or has a time column plus measures). Detection by column name, in priority order:

| Metric | Rule | additive | format |
|---|---|---|---|
| `revenue` | first of `amount`, `revenue`, `sales`, `net_sales`, `total`, `line_total` in the fact table; else `quantity × unit_price × (1 − discount)` if those columns exist | true | currency |
| `units` | `quantity`, `qty`, `units` | true | count |
| `orders` | `COUNT(DISTINCT <order id column>)` (column named `order_id` or the id column of the fact table) | true | count |
| `avg_order_value` | `revenue / orders` (ratio) | false | currency |
| `refunds` | `SUM(returns.refund_amount)` (or `refund*`/`return*` amount columns) | true | currency |
| `return_rate` | share of orders that have a return: `COUNT(DISTINCT CASE WHEN r.order_id IS NOT NULL THEN f.order_id END) / COUNT(DISTINCT f.order_id)` | false | percent |
| `stock_on_hand` | `SUM(inventory.stock_on_hand)`; `time_behavior: snapshot` | false | count |

Other numeric measure columns get a generic `sum_<column>` metric. Each metric has `label`, `synonyms` (from a built-in dictionary: revenue→sales/turnover/income; units→quantity/volume; orders→transactions; refunds→returns amount; stock_on_hand→inventory/stock), and `time_column` (the fact table's time column).

**Fields:**
- `time_behavior`: `flow` (default; sums across time are meaningful) or `snapshot` (values are levels at a date, e.g. inventory). Snapshot metrics take only the latest snapshot within each time bucket (see `query-plan-spec.md` section 7).
- `extra_joins`: list of `{table, on, mode}` for metrics that need another table without multiplying rows. `return_rate` uses `{"table": "returns", "on": "sales.order_id = returns.order_id", "mode": "distinct_semijoin"}`: the compiler left-joins `(SELECT DISTINCT order_id FROM returns)`.
- `expr` is parsed with sqlglot. Only columns of the metric's table are allowed (plus tables named in `extra_joins`); qualified names are rewritten to the fact alias.

## 7. Value index (`semantic/value_index.py`)
- Indexed: distinct values of `dimension` columns and entity `text` columns (up to 5,000 values per column), column display names, table display names, metric names and synonyms.
- Normalisation: lowercase, strip accents, collapse whitespace, strip punctuation.
- Lookup: exact match on normalised value, then fuzzy (rapidfuzz `WRatio`, score ≥ 85). For a question, generate 1-3 word n-grams and return candidates `{term, kind: value|column|metric, target, score}`.
- Ambiguity: if one term matches values in several columns, return all candidates and let the planner decide; the validator records fuzzy choices as assumptions.
- The special value `(missing)` matches null values.
- The index is rebuilt on upload and kept in memory; it is stored in `semantic.json` only as column-level counts, not values.

## 8. LLM enrichment (`semantic/enrich.py`, P1)
Input: table names, column names, dtypes, roles, up to 5 samples per column (only if `SEND_SAMPLES` is true and the column is not sample-suppressed), the metric list. Output (validated by Pydantic): `descriptions` per column, `synonyms` per metric, up to 3 `suggested_metrics` (each must reference existing columns; their `expr` is validated by sqlglot before acceptance). Any invalid output is discarded; failures are silent.

## 9. User edits (P1)
`PATCH /api/datasets/{id}/semantic` may change: column `role`, `description`; relationship `confirmed` (or removal); metric `label`, `synonyms`, `description`. Edits set `source: "user"` and survive rebuilds of the value index. Structural changes (role, relationships) trigger recomputation of the join graph and clear cached dashboards.

## 10. Tests
- Role tagging asserted for every column of the sample workbook.
- The four expected relationships found; no false positives; orphan product IDs reported.
- Metric expressions: `revenue` equals a pandas sum; `orders` counts distinct order ids; `return_rate` equals returned distinct orders ÷ distinct orders.
- Value index: "electronics", "west", "revnue" resolve as expected.
- `anchor_date` equals the maximum date in the primary time column.
