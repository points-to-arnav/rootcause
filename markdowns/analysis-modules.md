# analysis-modules.md: Why Engine, Dashboard Generator, Alerts

All computation is deterministic (DuckDB plus Python). The LLM only words the results. `architecture.md` sections 7-8 give the overview; this file is the working spec and wins on conflicts.

Thresholds live in `config.py`:

| Name | Default | Used for |
|---|---|---|
| `WHY_MAX_CARDINALITY` | 50 | max distinct segments for a candidate dimension |
| `WHY_MIN_SHARE` | 0.30 | min contribution of the top segment for a driver |
| `WHY_MIN_LIFT` | 1.5 | min lift for a driver |
| `WHY_MIN_CHANGE_PCT` | 1.0 | if the absolute percentage change is below this, report "essentially flat" |
| `WHY_OFFSET_RATIO` | 1.5 | offsetting flag when Σ\|δ\| > ratio × \|Δ\| |
| `ALERT_DROP_PCT` | 10 | KPI drop alert |
| `ALERT_Z` | 3 | anomaly alert |
| `ALERT_MIN_POINTS` | 8 | min periods for the anomaly test |
| `ALERT_CONCENTRATION` | 0.5 | one segment above this share of a metric |

## 1. Why engine (`analysis/why_engine.py`)
**Input:** `Plan` with `intent = why`: metric (additive), `time.range` (target window T), `comparison` (baseline window B; default `previous_period`), base `filters`, `why.dimensions` (null = all eligible), `why.max_depth`.

**Eligibility:** non-additive metric → validator error `NON_ADDITIVE_WHY`. For a ratio metric such as `avg_order_value` the pipeline may instead run the engine on numerator and denominator separately and report both (P1); in P0 the user is told it is unsupported.

**Steps**
1. **Totals.** `M(T)` and `M(B)` with base filters. `Δ = M(T) − M(B)`, `Δ% = Δ / |M(B)| × 100` (null if `M(B) = 0`). If `Δ = 0`, or `|Δ%| < WHY_MIN_CHANGE_PCT`, return `direction: "flat"` with the totals and stop.
2. **Candidate dimensions.** All dimension-role columns (and entity text columns for the final step only) reachable from the fact table with `2 ≤ distinct ≤ WHY_MAX_CARDINALITY`. Exclude ids, time columns, columns pinned by an equality/`in` filter, and constant columns. If `why.dimensions` is given, use only those.
3. **Per-dimension decomposition** (one query per dimension, one table scan):
```sql
SELECT COALESCE(CAST(d1."region" AS VARCHAR), '(missing)') AS "segment",
       COALESCE(SUM(f."amount") FILTER (WHERE f."order_date" >= ? AND f."order_date" < ?), 0) AS "target_value",
       COALESCE(SUM(f."amount") FILTER (WHERE f."order_date" >= ? AND f."order_date" < ?), 0) AS "baseline_value"
FROM "sales" AS f <joins> WHERE <time union window> [AND base filters]
GROUP BY 1
```
   For each segment s: `δ_s = target − baseline`; contribution `c_s = δ_s / Δ` (signed; may exceed ±1 when segments offset); baseline share `b_s = baseline_s / M(B)`; `lift_s = c_s / b_s` (if `b_s = 0`, the segment is new: lift is null and passes the lift test). **Invariant: Σ δ_s = Δ**, guaranteed by the `(missing)` bucket; assert it in tests and at runtime (tolerance 1e-6 relative).
4. **Driver test.** `c_top` is the largest `c_s` among segments moving in the direction of Δ (same sign as Δ). A dimension is a **driver** when `c_top ≥ WHY_MIN_SHARE` and the top segment's lift `≥ WHY_MIN_LIFT`. Rank drivers by `c_top` descending, ties by fewer segments. Non-drivers are reported as "no clear driver". If no dimension qualifies, `broad_based: true`.
5. **Offsetting flag.** `offsetting: true` when `Σ|δ_s| > WHY_OFFSET_RATIO × |Δ|` (segments cancel each other out). The narrator must mention it.
6. **Recursive drill.** Take the best driver dimension and its top segment; add it as a filter (`(missing)` → `IS NULL`); recompute `Δ` within it (equal to that segment's `δ`); repeat on the remaining dimensions until no dimension qualifies or depth reaches `why.max_depth` (default 3). Per step record `share_of_parent = δ_step / δ_parent` and `cumulative_share = δ_step / Δ_overall`.
7. **Top contributors.** At the deepest level, if an entity column exists (e.g. `products.product_name`), list the top N (default 5) entities by delta in the direction of Δ, with delta, share of the deepest-level delta, and cumulative share of the overall Δ. This answers "which five products drove the decline".
8. **(P1) Temporal localisation.** Split T into weeks (or days for windows ≤ 31 days) and report where the change concentrated.

**Output (`WhyResult`)**
```json
{
  "metric": "revenue", "direction": "decrease",
  "target":   {"start": "2026-08-01", "end": "2026-08-31", "value": 4100000},
  "baseline": {"start": "2026-07-01", "end": "2026-07-31", "value": 4850000},
  "delta": -750000, "delta_pct": -15.5, "broad_based": false, "offsetting": false,
  "dimensions": [
    {"dimension": "products.category", "is_driver": true, "c_top": 0.83, "lift": 4.2,
     "offsetting": false,
     "segments": [{"value": "Electronics", "target": 0, "baseline": 0,
                   "delta": -620000, "contribution": 0.83, "baseline_share": 0.20}]}
  ],
  "drill_path": [
    {"dimension": "products.category", "value": "Electronics",
     "delta": -620000, "share_of_parent": 0.83, "cumulative_share": 0.83},
    {"dimension": "customers.region", "value": "West",
     "delta": -590000, "share_of_parent": 0.95, "cumulative_share": 0.79}
  ],
  "top_contributors": {"dimension": "products.product_name",
                       "rows": [{"value": "...", "delta": -90000,
                                 "share_of_level": 0.15, "cumulative_share": 0.12}]}
}
```
(Numbers above are illustrative.) Direction is `increase`, `decrease` or `flat`. The narrator words the answer by direction, so the engine works for increases too.

**Edge cases**
- Segment in only one window: the missing window counts as 0.
- Baseline total is 0: `Δ%` null; lift skipped; only the share test applies.
- Negative values in the data are included as they are; their impact appears through data-quality warnings.
- Windows with no data: return a message stating the data range.
- Only one candidate dimension exists: run it; the drill stops after it.

**Chart:** signed contribution bars (see `viz-rules.md`), with the drill path shown as a breadcrumb list.

**Tests:** results equal pandas on the sample data; Σ δ_s = Δ including `(missing)`; offsetting synthetic case; a two-segment dimension with a 55/45 split is not a driver; increase and flat cases; the sample data yields the drill path Electronics → West with cumulative share of the August decline ≥ 70% and Electronics products as top contributors.

## 2. Dashboard generator (`analysis/dashboard.py`)
Endpoint: `POST /api/datasets/{id}/dashboard`. Goal: "Analyse this dataset and create a management dashboard."

**Reporting period:** the latest complete month before or at `anchor_date` (`current`) versus the month before it (`previous`). If the data spans less than 2 complete months, use `all` and skip comparisons.

**Panels** (each is a validated `Plan` run through compile → execute → viz selector):
1. **KPI cards (up to 6):** the fact table's default metrics in this order: `revenue`, `orders`, `units`, `avg_order_value`, `return_rate`, then other registry metrics. Each shows the current-period value, the change versus the previous period, and a sparkline (last 12 months of the metric by month).
2. **Trend:** primary metric by month over the full range.
3. **Breakdowns (2):** score every dimension reachable from the fact table:
   `score = 3 × [name matches region|category|segment|channel|type|status|country|state|city|department|brand] + 2 × [3 ≤ distinct ≤ 15] + 1 × [null_pct < 20]`; take the top 2 by score (ties: fewer distinct). Each is a bar chart of the primary metric for the current period, with previous-period comparison.
4. **Ranking:** top 10 of the main entity dimension (first entity column of the largest dimension table, e.g. product name) by the primary metric for the current period.
5. **Detail table (conditional):** records behind the highest-severity alert, when one exists (e.g. low-stock rows).

**Insights per panel:** deterministic one-liners built from the result (largest item and its share, change versus previous, best and worst). The narrator LLM is not required for them.

**Executive summary (optional):** 3-4 sentences from the LLM using only aggregated panel results, alerts and data-quality flags; verified by the number verifier; on any failure a templated summary is used.

**Planning with the LLM (optional):** the LLM may propose and order panel plans from the semantic layer; every proposed plan goes through the same validator and unsupported panels are dropped. If the LLM fails, the heuristic panel set above is used.

**Caching:** results cached per `(dataset_id, semantic version, reporting period)`; invalidated when semantic edits change structure. Target under 15 s uncached.

**Response:** `summary`, `period`, `kpis[]`, `panels[]` (`title`, `plan`, `sql`, `result`, `chart`, `insight`), `alerts[]`, `dq_warnings[]`. A user can open any panel in the analyst chat (the panel's plan becomes `current_plan`).

## 3. Alerts (`analysis/alerts.py`)
Alert record: `{id, severity: high|medium|low, type, title, detail, plan?}`.

| Type | Rule | Severity |
|---|---|---|
| `kpi_drop` | a KPI's change versus the previous period is below −`ALERT_DROP_PCT` % (for additive metrics; ratio metrics use percentage-point change ≥ 5) | high if below −2 × threshold, else medium |
| `anomaly` | latest complete period differs from the mean of the trailing periods (excluding itself) by more than `ALERT_Z` standard deviations; needs `ALERT_MIN_POINTS` periods | medium |
| `low_stock` | latest snapshot rows where `stock_on_hand ≤ reorder_level` (columns found by name: `stock|on_hand|in_stock` and `reorder|min_stock|threshold`); shows count and worst 10 by shortfall | high if any stock is 0, else medium |
| `concentration` | one segment of a breakdown holds more than `ALERT_CONCENTRATION` of the metric | low |
| `data_quality` | any high-severity data-quality issue | high |

Each alert with a drill-down attaches a `plan` so a click opens the analysis ("Why did revenue fall?" for `kpi_drop`). The alert text always states the period compared.

**Tests:** on the sample data, the August 2026 revenue `kpi_drop`, the Electronics/West `low_stock` alert, and the high-severity data-quality alerts appear; a stable dataset produces no `kpi_drop`.
