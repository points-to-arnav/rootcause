# implementation.md: Build Steps

Follow the phases in order. Each step has an ID that matches the checklist in `progress.md`. A step is done only when its **Done when** condition is met and its tests pass. Module names refer to the layout in `architecture.md` section 13.

Frontend work (Phase 7) can run in parallel from Phase 3 onward against mocked responses that follow `architecture.md` section 10.

---

## Phase 0: Setup (about 1 h)

**0.1 Scaffold**
- Create the folder structure, `.gitignore` (`backend/data/`, `.env`, `node_modules/`, `.venv/`, `__pycache__/`), `backend/.env.example`, and `backend/requirements.txt` (fastapi, uvicorn[standard], python-multipart, duckdb, pandas, openpyxl, pydantic, sqlglot, rapidfuzz, python-dotenv, pytest, httpx, anthropic).
- FastAPI app with `GET /api/health` and CORS for `http://localhost:5173`.
- Vite React + TypeScript app with Tailwind, ECharts, zustand; dev proxy `/api` → `http://localhost:8000`.
- **Done when:** both servers run and the frontend displays the response of `/api/health`.

**0.2 Config and LLM client**
- `app/config.py`: load `backend/.env` (path resolved relative to the file), expose settings from `CLAUDE.md` plus the thresholds used later (`WHY_MAX_CARDINALITY`, `WHY_MIN_SHARE`, `WHY_MIN_LIFT`, alert thresholds).
- `app/llm/client.py`: `complete_json(system, user, schema_model) -> BaseModel` using structured output/tool use; 30 s timeout; 2 retries with backoff; logs each call to `DATA_DIR/logs/llm.jsonl`.
- **Done when:** a unit test with a mocked provider passes, and a live smoke call returns a valid Pydantic object.

**0.3 Sample data**
- `sample_data/generate_retail.py` builds `sample_data/retail_demo.xlsx` per `plan.md` section 6 (seed 42, path relative to the script).
- **Done when:** the workbook has the 5 sheets, and a pandas check confirms August 2026 revenue is 15-20% below July 2026 and Electronics in West accounts for at least 70% of the drop, and that all planted data-quality issues are present.

---

## Phase 1: Ingestion and profiling

**1.1 Loader** (`ingestion/loader.py`)
- Accept `.xlsx` and `.csv`. Each sheet/file becomes a table; sanitise names to unique snake_case, keep `display_name`.
- Header-row detection (first row within the top 10 with at least 60% non-null text cells), drop fully empty rows and columns.
- Write to `DATA_DIR/{dataset_id}/data.duckdb`, then close the writer connection.
- **Done when:** the sample workbook yields 5 tables with correct row counts and a multi-CSV upload works.

**1.2 Type inference** (`profiling/types.py`)
- Choose BIGINT / DOUBLE / DATE / TIMESTAMP / BOOLEAN / VARCHAR per column. Try multiple date formats (ISO, `dd/mm/yyyy`, `mm/dd/yyyy`, `dd-Mon-yyyy`). Resolve `dd/mm` vs `mm/dd` from unambiguous rows (day > 12); if unresolved, default to day-first and flag it.
- Unparseable values become NULL and are counted in a data-quality issue with the formats found.
- **Done when:** the demo `sales.order_date` (mixed dates and text) parses to DATE for at least 98% of rows and the issue lists formats and counts.

**1.3 Profiler** (`profiling/profiler.py`)
- Per column: null count and percent, distinct count and ratio, min/max, mean/std for numerics, top 5 values, up to 5 samples. Compute in DuckDB SQL.
- **Done when:** profile values match independent pandas calculations on the sample data.

**1.4 Data-quality checks** (`profiling/quality.py`)
- Issue = `{id, severity, type, table, column, count, pct, message, impact}`. Types: `missing_values`, `duplicate_id`, `duplicate_rows`, `negative_values`, `outliers` (IQR × 3), `inconsistent_dates`, `constant_column`. (`orphan_keys` are added in 2.3.)
- `impact` states how answers are affected (e.g. "Rows with no region are grouped under '(missing)' in region breakdowns").
- **Done when:** every planted issue in the demo data is detected with correct counts.

**1.5 Upload endpoint**
- `POST /api/datasets`, `GET /api/datasets/{id}/quality` (schema comes from Phase 2). Response includes tables, profile, and issues.
- **Done when:** uploading the sample workbook through the API returns tables, profiles and issues; pytest covers the endpoint.

---

## Phase 2: Semantic layer

**2.1 Role tagging** (`semantic/tagger.py`): rules from `architecture.md` section 4. **Done when:** every sample column gets the expected role (asserted in a test).

**2.2 Relationship detection** (`semantic/relationships.py`): name/dtype compatibility, containment ≥ 0.95, unique parent key, confidence score. **Done when:** the four expected relationships (sales→customers, sales→products, returns→sales, inventory→products) are found and no false ones appear on the sample data.

**2.3 Join graph, fact table, orphan keys**: build the graph, pick the fact table, compute `anchor_date`, add `orphan_keys` data-quality issues. **Done when:** fact table = `sales`, `anchor_date` = 2026-08-31, and the orphan product IDs are reported.

**2.4 Metrics registry** (`semantic/metrics.py`): default metrics with `additive` flag, synonyms, format; cross-fact template for return rate. **Done when:** `revenue`, `units`, `orders`, `avg_order_value`, `return_rate` exist, and revenue matches a pandas sum.

**2.5 Value index** (`semantic/value_index.py`): exact and fuzzy lookup (score ≥ 85) over dimension values, column names, metric synonyms. **Done when:** "electronics", "west", "revnue" resolve to the right targets.

**2.6 LLM enrichment (P1, time-box 45 min)** (`semantic/enrich.py`): descriptions, synonyms and metric suggestions from names plus at most 5 samples (respect `SEND_SAMPLES`). Output validated by Pydantic; on any failure, skip silently. **Done when:** descriptions appear in the semantic JSON and the app works identically if enrichment is disabled.

**2.7 Persist and expose** (`semantic/store.py`): save/load `semantic.json`; `GET /api/datasets/{id}/semantic`; the upload response includes it. **Done when:** semantic layer survives a server restart.

---

## Phase 3: Planning and execution core

**3.1 Plan models** (`planner/plan_schema.py`): `Plan`, `Filter`, `TimeSpec`, `Comparison`, `PlannerOutput`, `PartialPlan` exactly as in `architecture.md` section 5, with model-level validation of the intent rules. **Done when:** valid and invalid plans are covered by tests.

**3.2 Time resolver** (`planner/timeutil.py`): resolve `last_n`, `calendar`, `between`, `all` to half-open windows using `anchor_date`; compute `previous_period` and `previous_year`. **Done when:** tests cover month and year boundaries, leap years, a partial trailing period (excluded), and `previous_year`.

**3.3 Validator** (`planner/validator.py`): columns exist and are reachable; aggregate valid for the column type; time column is a date; filter values resolved through the value index (fuzzy matches recorded as assumptions); intent rules enforced. Returns a list of errors usable for the repair call. **Done when:** each error class has a test.

**3.4 Compiler** (`planner/compiler.py`): plan → parameterised SQL per `architecture.md` section 6 (join path, unique dimension CTEs, `FILTER` conditional aggregation for comparisons, `date_trunc`, `(missing)` coalescing). **Done when:** a set of hand-written plans (kpi, trend, breakdown, ranking, compare with delta sort, filtered) produce results equal to independent pandas calculations on the sample data.

**3.5 Executor** (`planner/executor.py`): read-only connection, row cap, watchdog interrupt after `QUERY_TIMEOUT_S`. **Done when:** a deliberately slow query is interrupted and a row-capped result reports `truncated: true`.

**3.6 Planner** (`planner/planner.py`, `llm/prompts/planner.md`): retrieval → prompt → `PlannerOutput` → validate → repair loop (max 2). **Done when:** at least 15 golden questions (see `test-cases.md` when written; until then, a local list) produce plans whose executed results match expected values.

**3.7 `/ask` (single turn)** (`pipeline.py`, `api/routes_sessions.py`): `POST /api/sessions`, `POST /api/sessions/{sid}/ask` for kpi/trend/breakdown/ranking/compare/detail. **Done when:** "Show me monthly revenue for 2026" returns the correct rows and SQL from the real data.

---

## Phase 4: Visualisation and narration

**4.1 Viz selector** (`viz/selector.py`): rules from `architecture.md` section 9, output an ECharts option. **Done when:** each shape maps to the expected chart (table-driven tests).

**4.2 Narrator and verifier** (`narrator/*`, `llm/prompts/narrator.md`): input is plan, aggregated rows (≤ `NARRATOR_MAX_ROWS`), resolved time, DQ flags; output is 2-4 sentences. The verifier extracts numbers and checks them against the result (tolerating rounding, thousands separators, percent). One retry, then a templated summary. **Done when:** a test with a fabricated number fails verification and falls back to the template.

**4.3 Response assembler**: build `AskResponse`, tag `dq_warnings` (issues whose table.column is used by the plan or its filters), add deterministic follow-up `suggestions` by intent. **Done when:** an answer that groups by `customers.region` carries the missing-region warning with a quantified impact.

---

## Phase 5: Conversation

**5.1 Session state** (`memory/session.py`): state per `architecture.md` section 11, persisted after every turn, reloaded on restart. **Done when:** restarting the server keeps the session's current plan.

**5.2 Follow-up patching** (`memory/patcher.py`, planner prompt update): planner sees the current plan and returns `changes`; deterministic merge; re-validate. A clearly new question replaces the plan. **Done when:** unit tests cover replace, clear, `filters_add`, `filters_remove`, and intent change.

**5.3 Chain test:** "Show revenue by region." → "Only the last six months." → "Compare it with the previous six months." → "Which region contributed most to the decline?" **Done when:** the four turns yield breakdown → time-limited → compared → why(region) plans, and results match pandas.

---

## Phase 6: Why engine and dashboard

**6.1 Why engine core** (`analysis/why_engine.py`): steps 1-5 of `architecture.md` section 7. **Done when:** tests against pandas confirm Σ segment deltas = total delta (including the `(missing)` bucket), correct contributions and lift, the offsetting flag on a synthetic case, and correct handling of both increases and decreases.

**6.2 Recursive drill and top contributors**: steps 6-7. **Done when:** on the sample data the drill path is Electronics → West with cumulative share of the August decline at least 70%, and the top-5 contributing products are Electronics.

**6.3 Why narration and chart:** `why` intent wired into the pipeline, contribution chart and drill path in the response, narrator prompt handles `WhyResult`. **Done when:** "Why did revenue fall last month?" then "Was it mainly because of a particular product category?" then "Show me the five products responsible for the largest decline." each return the expected answer.

**6.4 Dashboard generator** (`analysis/dashboard.py`): panel plans, execution, viz specs, deterministic insights, optional LLM executive summary with template fallback; `POST /api/datasets/{id}/dashboard`. **Done when:** the sample workbook returns 4-6 KPIs, a monthly trend, two breakdowns, a top-10 ranking, in under 15 s.

**6.5 Alerts** (`analysis/alerts.py`): rules from `architecture.md` section 8. **Done when:** the August 2026 revenue drop, low stock for the affected Electronics products, and the high-severity data-quality issues appear as alerts.

---

## Phase 7: Frontend

**7.1 Upload and understanding view:** drag-and-drop upload, tables and columns with detected roles, relationship graph, data-quality report. **Done when:** the sample workbook shows all of that.

**7.2 Analyst chat:** chat thread, `ChartRenderer`, `KpiCard`, `ResultTable`, `PlanViewer` (plan, SQL, assumptions, resolved time), `DqBanner`, loading and error states. **Done when:** a full question-to-chart round trip works.

**7.3 Dashboard page:** KPI row, chart grid, alerts, summary, "Ask about this" on each panel. **Done when:** the generated dashboard renders from the real response.

**7.4 Polish:** suggestion chips, `needs_clarification` UI, table/chart toggle, empty-result states, consistent number formatting. **Done when:** the demo storyline runs without console errors.

---

## Phase 8: Hardening and submission

**8.1 Guarded fallback SQL (P1)** (`planner/fallback_sql.py`): per `architecture.md` section 6. **Done when:** a question outside plan expressiveness is answered via fallback, while a malicious statement (multi-statement, `DROP`, `read_csv`) is rejected in tests.

**8.2 Golden-question suite** (`backend/tests/`): all demo questions plus 15-20 more, each checked against pandas. **Done when:** the suite passes.

**8.3 Error handling:** empty results, unsupported questions, LLM timeout, clarification path, oversized uploads, bad files. **Done when:** no unhandled exceptions on any of these.

**8.4 Documentation:** `README.md` with setup, supported formats, architecture summary and diagram, and the AI-to-data workflow. **Done when:** a fresh clone can be set up from the README alone.

**8.5 Demo rehearsal:** run the storyline from `plan.md` section 6 twice end to end, record a backup screen capture, freeze the code. **Done when:** the recording exists and the tag for the demo commit is created.
