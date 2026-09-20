# query-plan-spec.md: Plan Schema, Validator, Compiler

The contract between the LLM planner and the deterministic engine. The planner never writes joins or raw SQL.

Where this file is more detailed than `architecture.md` sections 5-6, this file wins. Refinements: joins are `LEFT JOIN`; `previous_period` is calendar-aware; `delta_pct` is a percentage; `detail` intent rules; snapshot-metric compilation.

## 1. Pydantic models (`planner/plan_schema.py`)
```python
from datetime import date
from typing import Annotated, Literal, Optional, Union
from pydantic import BaseModel, Field, model_validator

Intent = Literal["kpi","trend","breakdown","ranking","compare","why","detail","dashboard"]
Agg = Literal["sum","avg","min","max","count","count_distinct"]
Op = Literal["=","!=","in","not_in",">",">=","<","<=","between","contains"]
Unit = Literal["day","week","month","quarter","year"]
Scalar = Union[str, int, float, bool]

class AdHocMetric(BaseModel):
    agg: Agg
    column: str                                   # "table.column"

class Filter(BaseModel):
    column: str
    op: Op
    value: Union[Scalar, list[Scalar], None]      # list for in/not_in/between ([lo, hi])

class LastN(BaseModel):
    type: Literal["last_n"]; unit: Unit; n: int = Field(ge=1, le=1000)
class Calendar(BaseModel):
    type: Literal["calendar"]; unit: Literal["month","quarter","year"]
    value: str                                    # "2026-08" | "2026-Q3" | "2026"
class Between(BaseModel):
    type: Literal["between"]; start: date; end: date   # end inclusive
class AllTime(BaseModel):
    type: Literal["all"]
TimeRange = Annotated[Union[LastN, Calendar, Between, AllTime], Field(discriminator="type")]

class TimeSpec(BaseModel):
    column: Optional[str] = None                  # default: metric's time_column
    range: Optional[TimeRange] = None
    grain: Optional[Unit] = None

class Comparison(BaseModel):
    type: Literal["previous_period","previous_year"]

class Sort(BaseModel):
    by: Literal["metric","delta","dimension","time"]
    dir: Literal["asc","desc"] = "desc"

class WhySpec(BaseModel):
    dimensions: Optional[list[str]] = None        # null = all eligible
    max_depth: int = Field(default=3, ge=1, le=4)

class Plan(BaseModel):
    intent: Intent
    metric: Union[str, AdHocMetric, None] = None
    dimensions: list[str] = []
    filters: list[Filter] = []
    time: Optional[TimeSpec] = None
    comparison: Optional[Comparison] = None
    sort: Optional[Sort] = None
    limit: Optional[int] = Field(default=None, ge=1)
    why: Optional[WhySpec] = None

class PlannerOutput(BaseModel):
    status: Literal["ok","needs_clarification","unsupported"]
    is_follow_up: bool = False
    plan: Optional[Plan] = None                   # new question
    changes: Optional[dict] = None                # follow-up (partial plan; see conversation-memory.md)
    message: Optional[str] = None
    assumptions: list[str] = []
```
Calendar `value` must match the unit: month `YYYY-MM`, quarter `YYYY-Qn` (n = 1-4), year `YYYY`.

## 2. Intent rules (enforced by `Plan` model validation)
| Intent | metric | dimensions | time | comparison | sort / limit |
|---|---|---|---|---|---|
| `kpi` | required | none | optional | optional | none |
| `trend` | required | 0-1 | `range` optional, **`grain` required** | not in P0 (overlay is P1) | sort by time asc |
| `breakdown` | required | 1-2 | optional | optional | default metric desc |
| `ranking` | required | exactly 1 | optional | optional | `limit` required (default 10); `sort.by` `metric` or `delta` |
| `compare` | required | 0-2 | `range` required | **required** | default metric desc |
| `why` | required, additive | none (use `why.dimensions`) | `range` required, not `all` | optional (baseline; default `previous_period`) | none |
| `detail` | optional (ignored) | 1-10 columns to display, any role | optional | none | `sort.by` `dimension` (first column) or `time`; `limit` default 100 |
| `dashboard` | none | none | none | none | none |

`sort.by = "delta"` requires `comparison`. `limit` is capped at `MAX_RESULT_ROWS`.

## 3. Validator (`planner/validator.py`)
Runs after merge (for follow-ups) and before time resolution. Returns `errors[]` and `warnings[]`; each item is `{code, message, path}`. Errors trigger the repair call (max 2); warnings become assumptions or notices.

| Code | Kind | Meaning |
|---|---|---|
| `UNKNOWN_METRIC` | error | metric name not in registry |
| `UNKNOWN_COLUMN` | error | `table.column` not in the semantic layer |
| `UNREACHABLE_TABLE` | error | column's table cannot be reached from the metric's fact table (max 3 many-to-one hops) |
| `BAD_AGG_FOR_TYPE` | error | e.g. `sum` on text, `avg` on id |
| `BAD_TIME_COLUMN` | error | time column not of role `time` |
| `MISSING_GRAIN` | error | `trend` without grain |
| `MISSING_COMPARISON` | error | `compare` without comparison |
| `MISSING_TIME_RANGE` | error | `compare` or `why` without a usable range |
| `DELTA_SORT_WITHOUT_COMPARISON` | error | |
| `BAD_INTENT_COMBO` | error | violates section 2 |
| `TOO_MANY_DIMENSIONS` | error | above the intent limit |
| `BAD_DIMENSION_ROLE` | error | role not eligible for group-by (see `semantic-layer.md` section 3) |
| `NON_ADDITIVE_WHY` | error | `why` on a non-additive metric (message explains; narrator offers numerator/denominator alternative) |
| `UNRESOLVED_FILTER_VALUE` | error | value not found exactly or fuzzily; message lists closest values |
| `FILTER_VALUE_FUZZY` | warning | value matched fuzzily; becomes an assumption ("'electronic' interpreted as 'Electronics'") |
| `AMBIGUOUS_VALUE` | error | value exists in several columns and the plan named none; message lists them (leads to clarification) |
| `RANGE_OUTSIDE_DATA` | warning | the resolved window does not overlap the data range; the result will be empty and the message states the data range |

Filter value resolution: exact normalised match first, then fuzzy (score ≥ 85), replaced by the canonical stored value. The value `"(missing)"` on `=`/`!=`/`in` means NULL.

## 4. Time resolution (`planner/timeutil.py`)
Anchor: `anchor_date` from the semantic layer (max date of the primary time column). Windows are half-open `[start, end)`.

**Completeness:** a calendar period is complete when `anchor_date` is on or after its last day. Week = ISO week (Monday start). Days are always complete.

| Range | Resolution |
|---|---|
| `last_n` (unit day) | the N days ending at `anchor_date` inclusive: `[anchor − N + 1, anchor + 1)` |
| `last_n` (week/month/quarter/year) | the N most recent **complete** units; if the unit containing `anchor_date` is incomplete it is excluded |
| `calendar` | that calendar unit, even if the data ends inside it (the UI notes a partial period) |
| `between` | `[start, end + 1 day)` |
| `all` | `[min, anchor + 1 day)` |

**Worked examples** (`anchor_date` = 2026-08-31, month-end, so August is complete):
- `last_n` 1 month → `[2026-08-01, 2026-09-01)` "Aug 2026".
- `last_n` 6 months → `[2026-03-01, 2026-09-01)`.
- `calendar` year 2026 → `[2026-01-01, 2027-01-01)` "2026 (partial: data ends 31 Aug)".
- With `anchor_date` = 2026-09-20 (mid-month): `last_n` 1 month → `[2026-08-01, 2026-09-01)`.

**Comparison windows:**
- `previous_period`: for windows aligned to months/quarters/years (including `last_n` of those and `calendar`), the same number of units immediately before (Aug 2026 → Jul 2026; last 6 months → the 6 months before). For day/week/`between` windows, the equal-length span of days immediately before the window.
- `previous_year`: both bounds shifted back 12 months (29 Feb clamps to 28 Feb).

The response's `resolved_time` gives `start`, `end` (inclusive date for display), `label`, and, for comparisons, the same for the baseline.

## 5. Compiler (`planner/compiler.py`)
Input: validated plan, semantic layer, resolved windows. Output: `(sql, params)` for DuckDB with `?` placeholders. Identifiers always double-quoted and taken from the semantic layer; `limit` is a validated integer inlined into the SQL.

**Aliases:** fact table `f`; dimension tables `d1`, `d2`, ... in first-use order.

**Joins:** for each non-fact table referenced (dimensions, filters), take the shortest many-to-one path from the fact table; emit `LEFT JOIN` so fact rows are never dropped (unmatched rows show as `(missing)`). If the joined table's key is not unique (profile shows distinct < non-null count), join a deduplicated subquery instead of the table:
```sql
LEFT JOIN (SELECT * FROM "customers"
           QUALIFY ROW_NUMBER() OVER (PARTITION BY "customer_id" ORDER BY rowid) = 1) AS d1
  ON f."customer_id" = d1."customer_id"
```
`extra_joins` with `distinct_semijoin`: `LEFT JOIN (SELECT DISTINCT "order_id" FROM "returns") AS x1 ON f."order_id" = x1."order_id"`.

**Metric expression:** parse `expr` with sqlglot, rewrite table-qualified columns to the fact alias, re-emit as DuckDB SQL. Ad-hoc metrics: `SUM(f."col")`, `COUNT(DISTINCT f."col")`, etc.

**Dimension expression:** `COALESCE(CAST(d1."region" AS VARCHAR), '(missing)')`. For non-string columns cast to VARCHAR only in the select/group expression.

**Filters (`WHERE`, ANDed):**
| Op | SQL |
|---|---|
| `=`, `!=`, `<`, `<=`, `>`, `>=` | `col op ?` (value `(missing)` → `col IS NULL` / `IS NOT NULL`) |
| `in`, `not_in` | `col IN (?, ?, ...)` / `NOT IN` (NULL handled with `IS NULL` OR-clause when `(missing)` is in the list) |
| `between` | `col BETWEEN ? AND ?` (inclusive) |
| `contains` | `col ILIKE '%' || ? || '%' ESCAPE '\'` with `%`, `_`, `\` escaped in the parameter |

**Time filter:** `f."<time col>" >= ? AND f."<time col>" < ?`. For comparisons the `WHERE` covers `[min(starts), max(ends))` and the precise windows go into `FILTER` clauses.

**Templates**
```sql
-- kpi
SELECT <metric_expr> AS "revenue"
FROM "sales" AS f
WHERE f."order_date" >= ? AND f."order_date" < ?

-- trend (grain month)
SELECT date_trunc('month', f."order_date") AS "period", <metric_expr> AS "revenue"
FROM "sales" AS f WHERE <time filter> [AND <filters>]
GROUP BY 1 ORDER BY 1

-- breakdown / ranking
SELECT <dim_expr> AS "region", <metric_expr> AS "revenue"
FROM "sales" AS f <joins> WHERE ... GROUP BY 1
ORDER BY "revenue" DESC [LIMIT n]

-- comparison (breakdown/ranking/compare/kpi)
SELECT *, "current" - "previous" AS "delta",
       CASE WHEN "previous" IS NULL OR "previous" = 0 THEN NULL
            ELSE ("current" - "previous") / ABS("previous") * 100 END AS "delta_pct"
FROM (
  SELECT <dim_expr> AS "region",
         COALESCE(<agg> FILTER (WHERE f."order_date" >= ? AND f."order_date" < ?), 0) AS "current",
         COALESCE(<agg> FILTER (WHERE f."order_date" >= ? AND f."order_date" < ?), 0) AS "previous"
  FROM "sales" AS f <joins> WHERE ... GROUP BY 1
) ORDER BY "delta" ASC        -- sort.by = delta
```
The `FILTER` form applies to aggregates of the form `AGG(expr)`; ratio metrics (`a / b`) apply `FILTER` inside each aggregate. `delta_pct` is in percent units (−15.2 means −15.2%). For `kpi` with comparison the inner query has no `GROUP BY`.

```sql
-- detail
SELECT f."order_id", d1."region", ...
FROM "sales" AS f <joins> WHERE ... ORDER BY f."order_date" DESC LIMIT 100
```

**Gap filling (P1):** for additive metrics in `trend`, missing periods are filled with 0 using a generated period series; for ratios and averages they stay NULL.

## 6. Cross-fact and multi-hop cases
- A plan has one fact table: the metric's table. Dimensions may come from any table reachable through many-to-one edges, including through intermediate tables (`refunds` by `products.category` goes `returns → sales → products`).
- A metric that needs another fact table uses `extra_joins` (as `return_rate`).
- Asking for two metrics from different fact tables in one plan is not supported in P0; the planner returns `unsupported` or two separate answers.

## 7. Snapshot metrics (`time_behavior: snapshot`, e.g. `stock_on_hand`)
Sum across dimensions but never across time. Before aggregating, keep only the latest snapshot in each time bucket:
```sql
-- trend, grain month
SELECT date_trunc('month', s."snapshot_date") AS "period", SUM(s."stock_on_hand") AS "stock_on_hand"
FROM (
  SELECT * FROM "inventory" WHERE <time filter>
  QUALIFY "snapshot_date" = MAX("snapshot_date") OVER (PARTITION BY date_trunc('month', "snapshot_date"))
) AS f <joins> ... GROUP BY 1 ORDER BY 1
```
Without a grain (kpi, breakdown), `PARTITION BY` is omitted so only the latest snapshot in the window is used. The narrator states "as of <date>".

## 8. Fallback SQL (P1, `planner/fallback_sql.py`)
Used when the planner returns `unsupported` for a question that is answerable from the data (e.g. column-versus-column conditions like stock below reorder level).
1. Prompt with the semantic schema; LLM returns `{sql, explanation}`.
2. Parse with sqlglot (`dialect="duckdb"`); reject unless exactly one statement whose root is `SELECT` (CTEs allowed).
3. Every table must be in the dataset; reject any table function (`read_csv`, `read_parquet`, `glob`, etc.), `COPY`, `ATTACH`, `PRAGMA`, `SET`, DDL/DML.
4. Execute on a read-only connection with `enable_external_access=false` if supported when opening the file, plus the row cap and timeout.
5. On execution error, at most 2 repair calls with the error text.
6. The response carries `plan: null`, `sql`, and a notice "Answered with generated SQL (no structured plan)".

## 9. Tests
- Plan model: valid and invalid combinations for every intent rule.
- Time resolver: month/quarter/year boundaries, leap year, partial trailing period, mid-month anchor, `previous_year` on 29 Feb.
- Validator: one test per error and warning code.
- Compiler: hand-written plans for kpi, trend, breakdown, ranking, compare with delta sort, filtered, `(missing)` bucket, dedup join, multi-hop, `return_rate`, snapshot trend; every result equals an independent pandas computation.
- Injection: filter values containing quotes, `%`, `;` and SQL keywords are bound safely and never change the statement.
