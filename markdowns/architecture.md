# architecture.md: AskData

## 1. Design principle
The LLM is a **planner and narrator**. It never sees raw rows and never does math. A deterministic engine (DuckDB plus Python analysis modules) does all computation. Everything the LLM produces is structured, validated, and inspectable.

## 2. System diagram
```
 Excel / CSV upload
        │
        ▼
 ┌─────────────┐   ┌────────────┐   ┌──────────────────────┐
 │  Ingestion  │──▶│  Profiler  │──▶│ Semantic layer (JSON)│◀── LLM enrichment (names + samples only)
 │  → DuckDB   │   │ + DQ checks│   │ roles, joins, metrics│
 └─────────────┘   └────────────┘   │ value index          │
                                    └──────────┬───────────┘
                                               │ schema context
 Question + session state ─▶ LLM Planner ◀─────┘
                                │  PlannerOutput (JSON)
                                ▼
                 Merge (follow-up patch) ─▶ Validator ─▶ Time resolver
                                │
              ┌─────────────────┼──────────────────┐
              ▼                 ▼                  ▼
        SQL compiler       Why engine      Dashboard generator
              │                 │                  │
              └────────────▶ DuckDB (read-only) ◀──┘
                                │ result tables
                                ▼
                     Viz selector (rules) ─▶ ECharts option
                                │
                                ▼
              LLM Narrator (aggregates only) ─▶ number verifier
                                │
                                ▼
       AskResponse: plan · sql · result · chart · narrative · dq_warnings
```

## 3. Components
| Component | Module | Responsibility | Uses LLM |
|---|---|---|---|
| Ingestion | `ingestion/loader.py` | Each Excel sheet / CSV becomes a DuckDB table; header-row detection; name sanitising | No |
| Type inference | `profiling/types.py` | Numeric/date/boolean/text inference, multi-format date parsing | No |
| Profiler | `profiling/profiler.py` | Per-column stats: nulls, distinct, min/max, top values, samples | No |
| Data quality | `profiling/quality.py` | Issue detection with severity and impact statement | No |
| Semantic layer | `semantic/*` | Column roles, relationships, join graph, metrics, value index | Optional enrichment |
| Planner | `planner/planner.py` | Question + context → `PlannerOutput` | Yes |
| Follow-up patcher | `memory/patcher.py` | Deterministic merge of `changes` into the current plan | No |
| Validator | `planner/validator.py` | Checks plan against semantic layer; resolves filter values | No |
| Time resolver | `planner/timeutil.py` | Relative/calendar ranges → concrete half-open windows using `anchor_date` | No |
| Compiler | `planner/compiler.py` | Plan → parameterised DuckDB SQL using the join graph | No |
| Executor | `planner/executor.py` | Read-only execution, row cap, timeout | No |
| Fallback SQL | `planner/fallback_sql.py` | Guarded LLM-written SQL with repair loop (P1) | Yes |
| Why engine | `analysis/why_engine.py` | Delta decomposition and recursive drill-down | No |
| Dashboard generator | `analysis/dashboard.py`, `analysis/alerts.py` | Panel plans, execution, alert rules | Optional |
| Viz selector | `viz/selector.py` | Result shape → chart type → ECharts option | No |
| Narrator | `narrator/narrator.py`, `narrator/verify.py` | Aggregates → short explanation; numbers verified | Yes |
| Pipeline | `pipeline.py` | Orchestrates the `/ask` lifecycle | No |

## 4. Semantic layer
Stored as `DATA_DIR/{dataset_id}/semantic.json`. Shape:
```json
{
  "dataset_id": "ds_ab12",
  "tables": {
    "sales": {
      "display_name": "Sales", "row_count": 18000, "role": "fact",
      "columns": {
        "amount": {
          "display_name": "Amount", "dtype": "DOUBLE", "role": "measure",
          "description": "Order value after discount",
          "null_pct": 0.0, "distinct": 9421, "min": 5.0, "max": 98000.0,
          "samples": [120.5, 999.0]
        }
      }
    }
  },
  "relationships": [
    {"from": "sales.customer_id", "to": "customers.customer_id",
     "type": "many_to_one", "confidence": 0.97, "confirmed": false}
  ],
  "metrics": [
    {"name": "revenue", "expr": "SUM(sales.amount)", "table": "sales",
     "additive": true, "format": "currency", "synonyms": ["sales", "turnover"]}
  ],
  "time": {"primary_column": "sales.order_date", "min": "2025-01-01",
           "max": "2026-08-31", "anchor_date": "2026-08-31"},
  "quality_issues": []
}
```
**Column roles:** `id`, `time`, `measure`, `dimension`, `text`.
- `time`: DATE/TIMESTAMP dtype.
- `id`: name matches `id`/`key`/`code` pattern with high distinct ratio, or unique values.
- `measure`: numeric, not id (price, quantity, amount, cost...).
- `dimension`: string or low-cardinality column (distinct ≤ max(50, 5% of rows)).
- `text`: high-cardinality free text (names, comments); not used for grouping except as a ranking entity (e.g. product_name).

**Relationships:** candidate pair when column names normalise equal (or `<table>_id` pattern) and dtypes are compatible. Accept when containment (share of child distinct values found in parent) ≥ 0.95 and the parent column is a candidate key (uniqueness ≥ 0.99). Confidence combines name match, containment and uniqueness. Orphan child values are recorded as a data-quality issue.

**Fact table:** the table with the most rows that is child in the most many-to-one relationships and has a date plus measures. It is the primary anchor for joins and `anchor_date`. Other fact-like tables (Returns, Inventory) are separate. **A plan uses one fact table**; cross-fact metrics (e.g. return rate) are named metrics defined with pre-aggregated CTE templates.

**Metrics registry:** auto-generated defaults (revenue, quantity/units, order count, average order value, and cross-fact templates when the tables exist). Each has `additive` (true for sum/count, false for ratios/averages).

**Value index:** normalised distinct values of dimension columns (up to 5,000 per column) plus column display names and metric synonyms. Lookup is exact, then fuzzy (rapidfuzz score ≥ 85). Maps "electronics" to `products.category = 'Electronics'`.

## 5. Query plan
The planner never writes joins or raw SQL.

| Field | Type | Notes |
|---|---|---|
| `intent` | enum | `kpi`, `trend`, `breakdown`, `ranking`, `compare`, `why`, `detail`, `dashboard` |
| `metric` | string or `{agg, column}` | Name from `semantic.metrics`, or ad-hoc aggregate (`sum`, `avg`, `min`, `max`, `count`, `count_distinct`) over one column |
| `dimensions` | list of `table.column` | Group-bys, max 2 |
| `filters` | list of `{column, op, value}` | ops: `=`, `!=`, `in`, `not_in`, `>`, `>=`, `<`, `<=`, `between`, `contains` |
| `time` | `{column, range, grain}` or null | `column` defaults to the fact table's primary date column |
| `time.range` | union | `{"type":"last_n","unit":"month","n":6}`; `{"type":"calendar","unit":"month\|quarter\|year","value":"2026-08"}` (also `"2026-Q3"`, `"2026"`); `{"type":"between","start":"YYYY-MM-DD","end":"YYYY-MM-DD"}` (end inclusive); `{"type":"all"}` |
| `time.grain` | enum or null | `day`, `week`, `month`, `quarter`, `year` |
| `comparison` | `{type}` or null | `previous_period` (the immediately preceding window of equal length) or `previous_year` (window shifted 12 months) |
| `sort` | `{by, dir}` | `by`: `metric`, `delta`, `dimension`, `time`; `dir`: `asc`, `desc` |
| `limit` | int | default 10 for ranking; max `MAX_RESULT_ROWS` |
| `why` | `{dimensions, max_depth}` or null | only for `why`; `dimensions` null means all eligible; `max_depth` default 3 |

Rules:
- `trend` requires `time.grain`. `kpi` has no dimensions. `ranking` requires exactly one dimension and a limit. `compare` requires `comparison`. `why` requires a non-`all` `time.range`; its baseline is `comparison` if given, else `previous_period`.
- `comparison` is supported for `kpi`, `breakdown`, `ranking`, `compare` and `why`. Comparison results carry `current`, `previous`, `delta`, `delta_pct`. Trend overlay is P1.
- `sort.by = delta` is valid only when `comparison` is set (e.g. "five products responsible for the largest decline").
- All columns are `table.column`, must exist, and must be reachable from the fact table via the join graph.

**PlannerOutput** (what the LLM returns):
```json
{
  "status": "ok | needs_clarification | unsupported",
  "is_follow_up": false,
  "plan": {},
  "changes": null,
  "message": null,
  "assumptions": ["'revenue' = SUM(sales.amount)"]
}
```
`plan` is set for a new question; `changes` (a partial plan) is set for a follow-up. `message` carries the clarification question or the reason for `unsupported`. `assumptions` are shown in the UI.

**Follow-up merge rules (deterministic, `memory/patcher.py`):**
- Fields present in `changes` replace the current value; an explicit `null` clears the field.
- `filters_add` appends filters (replacing an existing filter on the same column and op); `filters_remove` lists columns whose filters are removed.
- If `intent` changes, fields invalid for the new intent are dropped (e.g. `limit` for `kpi`).
- The merged plan goes through the validator again.

Example chain: "Show revenue by region." (breakdown by `customers.region`) → "Only the last six months." (`time.range` = `last_n` 6 months) → "Compare it with the previous six months." (`comparison` = `previous_period`) → "Which region contributed most to the decline?" (`intent` = `why`, `why.dimensions` = `["customers.region"]`).

## 6. Request lifecycle (`POST /api/sessions/{sid}/ask`)
1. Load session state (current plan, history) and the semantic layer.
2. **Retrieve values:** fuzzy-match n-grams of the question against the value index → candidate `(column, value)` pairs.
3. **Build the planner prompt:** compact schema (tables, columns with role and description), metrics with synonyms, join summary, data range and `anchor_date`, current plan, candidate matches, the question.
4. **Call the LLM** for `PlannerOutput` (Pydantic-validated). Handle `needs_clarification` / `unsupported` by returning the message.
5. **Merge** (if follow-up) → **validate** → **resolve time**. On validation errors, one repair call with the error list (max 2 attempts), then return a clear failure.
6. **Route by intent:** `why` → why engine; `dashboard` → dashboard generator; everything else → compiler → executor.
7. **Post-process:** viz selector builds the ECharts option; data-quality issues touching the plan's columns become `dq_warnings`; narrator writes the explanation from plan + aggregates + flags; verifier checks numbers.
8. **Assemble** `AskResponse`, update and persist session state.

Target: 2 LLM calls per question, about 8 s or less for simple questions.

**Compiler details**
- Joins: from the fact table to each needed dimension table along the shortest path in the join graph (many-to-one only).
- Dimension keys are made unique with `QUALIFY ROW_NUMBER() OVER (PARTITION BY key ORDER BY rowid) = 1` when the key is not unique, so joins cannot multiply fact rows. The duplicate key is reported as a data-quality issue.
- Comparison plans use one scan with conditional aggregation: `SUM(x) FILTER (WHERE d >= t_start AND d < t_end) AS current` and the same for `previous`, over a `WHERE` covering both windows.
- Time windows are half-open `[start, end)`. `last_n` means the last N complete calendar units ending at or before `anchor_date`; a trailing partial unit is excluded and the UI states the resolved range.
- Grain uses `date_trunc`. Null dimension values are coalesced to `'(missing)'`.
- Filter values and window bounds are bound parameters.

**Executor:** read-only connection (`duckdb.connect(path, read_only=True)`), row cap, and a watchdog thread that calls `connection.interrupt()` after `QUERY_TIMEOUT_S`. Do not open the same DuckDB file with mixed read/write configurations in one process: the ingestion writer connection is closed before any read-only connection opens.

**Fallback SQL (P1):** when the plan cannot express a question, the LLM writes a single SELECT. It is parsed with sqlglot (dialect `duckdb`), rejected unless it is one SELECT/WITH-SELECT, every table is whitelisted, and no table functions appear (no `read_csv`, `read_parquet`, etc.). It runs on a read-only connection with the row cap and timeout; also set `enable_external_access=false` on that connection (verify it still opens the database file in the installed DuckDB version; if not, rely on the sqlglot checks plus read-only). On an execution error, up to 2 repair calls. The response marks it as `fallback` in the UI.

## 7. Why / drill-down engine (`analysis/why_engine.py`)
**Inputs:** additive metric, target window T, baseline window B (default `previous_period`), base filters, candidate dimensions.

1. **Total change:** Δ = M(T) − M(B). If both are zero or Δ = 0, report "no change".
2. **Candidate dimensions:** dimension-role columns reachable from the fact table with 2 ≤ distinct ≤ `WHY_MAX_CARDINALITY` (default 50). Exclude ids, text, time columns, and columns already pinned by an equality filter.
3. **Per dimension d:** one grouped query returns `M_T(s)` and `M_B(s)` per segment s (conditional aggregation; null values in the `(missing)` bucket).
   - Segment delta δ_s = M_T(s) − M_B(s). Invariant: Σ δ_s = Δ.
   - Contribution c_s = δ_s / Δ (signed; can exceed ±100% when segments offset).
   - Baseline share b_s = M_B(s) / M_B(total). Lift_s = c_s / b_s.
4. **Score and qualify:** c_top is the largest contribution among segments moving in the direction of Δ. Dimension d is a **driver** if c_top ≥ `WHY_MIN_SHARE` (0.30) and its lift ≥ `WHY_MIN_LIFT` (1.5). Rank drivers by c_top descending, ties by lower cardinality. Non-drivers are listed as "no clear driver". If no dimension qualifies, report the change as broad-based.
5. **Offsetting flag:** set when Σ|δ_s| > 1.5 × |Δ| (segments cancel each other out).
6. **Recursive drill:** take the top driver dimension and its top segment; add it as a filter; recompute Δ within that segment; repeat on the remaining dimensions until no dimension qualifies or depth reaches `max_depth` (default 3). Report each step's share of the parent delta and its **cumulative** share of the overall Δ (= segment delta at that depth ÷ overall Δ).
7. **Top contributors:** at the deepest level, and when a product-like entity column exists, the top-N entities by delta in the direction of Δ ("five products responsible for the largest decline").

**Output** (`WhyResult`): `metric`, `direction` (`decrease`/`increase`), `target` and `baseline` (window, value), `delta`, `delta_pct`, `dimensions[]` (each with `c_top`, `lift`, `is_driver`, `offsetting`, `segments[]`), `drill_path[]` (`dimension`, `value`, `delta`, `share_of_parent`, `cumulative_share`), `top_contributors`.

The narrator words the result by direction (fell/rose), so the engine works for increases as well as decreases. For non-additive metrics, see `CLAUDE.md` rule 10.

P1: temporal localisation (which weeks or days inside T drove the change). P2: price/volume/mix split.

## 8. Dashboard generator and alerts
`POST /api/datasets/{id}/dashboard` builds a list of panel plans, runs each through compile → execute, and attaches a viz spec:
- **KPI cards (up to 6):** default metrics, value for the latest complete period, change versus the previous period, with a sparkline.
- **Trend:** primary metric by month across the full range.
- **Breakdowns:** the two most informative dimensions (3-15 distinct values, business-named) by primary metric.
- **Rankings:** top 10 for the main entity dimension (e.g. product, customer).
- **Detail table:** the records behind the top alert, when one exists.
- **Alerts:** rules with thresholds in `config.py`:
  - KPI drop of more than 10% versus the previous period.
  - Latest period value with |z| > 3 against the trailing periods (needs at least 8 periods).
  - Low stock: `stock_on_hand ≤ reorder_level` when those columns exist.
  - One segment holding more than 50% of a metric.
  - High-severity data-quality issues.
- **Executive summary (optional):** 3-4 sentences from the LLM using aggregates only. If the LLM fails, the panel set and a templated summary are still returned. The LLM may propose or order panel plans, but they pass through the same validator.

## 9. Visualisation selector (`viz/selector.py`)
| Result shape | Output |
|---|---|
| 1 row, 1 measure | KPI card (with delta and percentage when compared) |
| time + 1 measure | Line chart |
| time + measure + 1 dimension | Multi-line (up to 6 series; otherwise top 5 plus "Other") |
| 1 dimension + measure, ≤ 12 categories | Vertical bar |
| ranking, top-N, > 12 categories, or long labels | Horizontal bar, sorted |
| comparison by dimension | Grouped bar (current vs previous) |
| `why` result | Signed contribution bar (diverging colours), plus drill path panel |
| detail records or > 2 dimensions | Table |

A table view is always available as a toggle. No pie charts by default.

## 10. API contract (draft; freeze early because the frontend depends on it)
All under `/api`.

| Method and path | Purpose |
|---|---|
| `GET /health` | Liveness |
| `POST /datasets` (multipart `files[]`) | Upload and ingest; returns `dataset_id`, tables, relationships, DQ summary |
| `GET /datasets/{id}/semantic` | Semantic layer |
| `PATCH /datasets/{id}/semantic` | Edit roles, descriptions, metrics; confirm/reject relationships (P1) |
| `GET /datasets/{id}/quality` | Data-quality issues |
| `POST /sessions` `{dataset_id}` | Create a session; returns `session_id` |
| `POST /sessions/{sid}/ask` `{question}` | Ask a question; returns `AskResponse` |
| `GET /sessions/{sid}/history` | Previous turns |
| `POST /datasets/{id}/dashboard` `{session_id?}` | Generate dashboard; returns `DashboardResponse` |

`AskResponse`:
```json
{
  "status": "ok | needs_clarification | unsupported | error",
  "message": null,
  "plan": {},
  "assumptions": [],
  "resolved_time": {"start": "2026-08-01", "end": "2026-08-31", "label": "Aug 2026"},
  "sql": "SELECT ...",
  "result": {"columns": [], "rows": [], "row_count": 0, "truncated": false},
  "chart": {"type": "line", "echarts_option": {}},
  "narrative": "",
  "dq_warnings": [{"severity": "medium", "message": "", "affected": ["customers.region"]}],
  "why": null,
  "suggestions": []
}
```
`DashboardResponse`: `summary`, `kpis[]`, `panels[]` (each with `title`, `plan`, `sql`, `result`, `chart`, `insight`), `alerts[]`, `dq_warnings[]`.

## 11. Storage and sessions
- Per dataset: `DATA_DIR/{dataset_id}/data.duckdb` and `semantic.json`.
- Sessions: kept in memory and **persisted to `DATA_DIR/{dataset_id}/sessions/{sid}.json` after every turn**, because `uvicorn --reload` wipes memory on code changes. Session = `session_id`, `dataset_id`, `current_plan`, and `history` (last 20 turns: question, plan, one-line result summary, timestamp).
- LLM calls are logged to `DATA_DIR/logs/llm.jsonl` for debugging.
- No separate application database.

## 12. Safety and correctness guards
- LLM data exposure limited as listed in `CLAUDE.md` rule 2.
- Validated identifiers only; parameters for values; fallback SQL restricted (section 6).
- Numbers in narratives are checked against the result table.
- Data-quality decisions: **negative values and duplicate rows are kept and reported with a quantified impact** (P1 adds an exclude-duplicates toggle). Rows excluded for null or unparseable dates are counted in the response.
- Relative time anchored to the data (`anchor_date`).
- Result caps and timeouts on every query.

## 13. Folder structure
```
askdata/
├── CLAUDE.md
├── README.md
├── plan.md
├── architecture.md
├── implementation.md
├── progress.md
├── .gitignore
├── sample_data/
│   ├── generate_retail.py
│   └── retail_demo.xlsx                 (generated)
├── backend/
│   ├── requirements.txt
│   ├── .env.example
│   ├── data/                            (gitignored: datasets, sessions, logs)
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── pipeline.py
│   │   ├── api/            routes_datasets.py, routes_sessions.py, routes_dashboard.py
│   │   ├── ingestion/      loader.py
│   │   ├── profiling/      types.py, profiler.py, quality.py
│   │   ├── semantic/       model.py, tagger.py, relationships.py, metrics.py,
│   │   │                   value_index.py, enrich.py, store.py
│   │   ├── planner/        plan_schema.py, timeutil.py, validator.py, compiler.py,
│   │   │                   executor.py, planner.py, fallback_sql.py
│   │   ├── memory/         session.py, patcher.py
│   │   ├── analysis/       why_engine.py, dashboard.py, alerts.py
│   │   ├── viz/            selector.py
│   │   ├── narrator/       narrator.py, verify.py
│   │   └── llm/            client.py, prompts/ (planner.md, narrator.md, enrich.md, dashboard.md)
│   └── tests/
└── frontend/
    ├── package.json
    └── src/
        ├── main.tsx, App.tsx, types.ts, api.ts, store.ts
        ├── pages/          UploadPage.tsx, AnalystPage.tsx, DashboardPage.tsx
        └── components/     ChartRenderer, KpiCard, ResultTable, PlanViewer,
                            DqBanner, RelationshipGraph, SuggestionChips
```

## 14. Tech stack
- **Backend:** Python 3.11+, FastAPI, DuckDB, pandas + openpyxl (ingestion), Pydantic v2, sqlglot, rapidfuzz.
- **LLM:** provider behind `llm/client.py`; structured output through tool use / JSON schema.
- **Frontend:** React + Vite + TypeScript, Tailwind CSS, ECharts, zustand. Vite dev server on 5173 proxies `/api` to 8000; FastAPI allows CORS from `http://localhost:5173`.
- **Supported formats:** `.xlsx` and `.csv` (P0); `.xls` and `.tsv` (P1).

## 15. Key decisions and trade-offs
| Decision | Why | Trade-off |
|---|---|---|
| JSON plan instead of free SQL | Validatable, safe, explainable, enables patch-style follow-ups | Less expressive; fallback SQL covers the gap (P1) |
| DuckDB file per dataset | Fast analytics, read-only connections, simple | Single-process, no multi-user |
| Anchor date from data | Correct answers for historical files | Users see the resolved range explicitly |
| Trailing partial period excluded | Avoids misleading "drops" | Latest partial data not shown in KPIs |
| Keep duplicates and negatives, but report | Never silently alter user data | Numbers may include problem rows until user chooses |
| Rule-based viz selection | Deterministic and testable | Less flexible than LLM-chosen charts |
| Driver test uses share and lift | Avoids trivial winners on 2-segment dimensions | Two thresholds to tune |
