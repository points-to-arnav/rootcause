# RootCause / AskData: Comprehensive Architecture & System Guide

## 1. Project Philosophy & Core Invariants

RootCause (AskData) is a deterministic, conversational AI data analyst platform. It eliminates LLM hallucinations in quantitative analysis by adhering strictly to three core rules:

1. **LLM as Planner & Narrator Only**:
   - The LLM translates user natural language into structured JSON execution plans (`PlannerOutput` & `Plan`).
   - The LLM explains pre-computed aggregates in 2–4 concise sentences.
   - The LLM **never** computes sums, averages, deltas, or percentages.
2. **DuckDB Executes All Math**:
   - Every metric, aggregation, filter, and multi-table join is compiled into high-performance, single-scan DuckDB SQL or computed deterministically in Python.
   - Raw table rows are never piped into prompt contexts.
3. **Number Verification Gate**:
   - Every number, currency figure, and percentage generated in the narrator text is extracted via regex and matched against the actual DuckDB result table cells.
   - If an unverified or hallucinated number is found, the system rejects the text and falls back to a deterministic templated narrative.

---

## 2. Directory Structure & File Map

```
rootcause/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── routes_datasets.py   # Dataset upload, sample loading, schema & DQ endpoints
│   │   │   ├── routes_sessions.py   # Conversational session management & /ask pipeline endpoint
│   │   │   ├── routes_dashboard.py  # One-call executive management dashboard generator
│   │   │   └── routes_settings.py   # Runtime settings & health check
│   │   ├── ingestion/
│   │   │   └── loader.py            # Multi-sheet Excel & CSV ingestion, header detection, DuckDB tables
│   │   ├── profiling/
│   │   │   ├── types.py             # Type inference (BIGINT, DOUBLE, DATE, VARCHAR) & column casting
│   │   │   ├── profiler.py          # Column statistics, quantiles, distinct ratios, PII suppression
│   │   │   └── quality.py           # 7 automated data quality checks (missing, duplicates, negative, etc.)
│   │   ├── semantic/
│   │   │   ├── model.py             # SemanticLayer, TableMeta, ColumnMeta, Relationship, Metric schemas
│   │   │   ├── tagger.py            # Automatic column role classification (id, time, measure, dimension)
│   │   │   ├── relationships.py     # Foreign key candidate pairing, uniqueness & containment scoring
│   │   │   ├── join_graph.py        # Graph pathfinding, fact table selection, anchor_date computation
│   │   │   ├── metrics.py           # Standard business metric auto-registration (revenue, units, etc.)
│   │   │   ├── value_index.py       # RapidFuzz in-memory indexing of dimensional terms & metric synonyms
│   │   │   └── store.py             # Persistence of semantic layers to JSON
│   │   ├── planner/
│   │   │   ├── plan_schema.py       # Pydantic models for Plan, Filter, TimeSpec, Comparison, WhySpec
│   │   │   ├── timeutil.py          # Relative time resolution anchored to anchor_date
│   │   │   ├── validator.py         # Schema constraint validation & intent healing
│   │   │   ├── compiler.py          # Plan-to-DuckDB SQL compiler with single-scan FILTER aggregation
│   │   │   ├── executor.py          # Read-only DuckDB execution with query watchdog timeout
│   │   │   └── planner.py           # Few-shot LLM planner with RapidFuzz value matching injection
│   │   ├── memory/
│   │   │   ├── session.py           # Session persistence & conversational turn history
│   │   │   └── patcher.py           # Partial plan patcher for follow-up conversational questions
│   │   ├── analysis/
│   │   │   ├── why_engine.py        # Period-over-period delta decomposition & driver qualification
│   │   │   ├── alerts.py            # Automated anomaly and threshold alert rules
│   │   │   └── dashboard.py         # Multi-panel executive dashboard generator
│   │   ├── viz/
│   │   │   └── selector.py          # Rule-based chart selector (KPI, line, bar, bar_h, grouped_bar, contribution)
│   │   ├── narrator/
│   │   │   ├── narrator.py          # 2-4 sentence business narrative synthesis
│   │   │   └── verify.py            # Strict number verification against DuckDB output cells
│   │   ├── llm/
│   │   │   ├── client.py            # Dual-provider client (OpenRouter primary, NVIDIA NIM fallback)
│   │   │   └── prompts/             # System prompts for planner, narrator, repair, dashboard
│   │   ├── config.py                # Environment and configuration settings
│   │   ├── main.py                  # FastAPI application entry point with CORS and error handlers
│   │   └── pipeline.py              # End-to-end question processing pipeline
│   ├── tests/                       # Pytest test suite (compiler, why engine, pipeline, narrator, API)
│   ├── requirements.txt             # Python dependencies
│   └── .env                         # Provider keys and runtime configs
│
├── frontend/
│   ├── src/
│   │   ├── api/
│   │   │   └── client.ts            # Typed HTTP client for all backend REST endpoints
│   │   ├── components/
│   │   │   ├── Navbar.tsx           # Header with branding, tab switcher, model indicator, settings modal
│   │   │   ├── ChartRenderer.tsx    # Dynamic ECharts wrapper (line, bar, grouped bar, contribution, KPI)
│   │   │   ├── PlanViewer.tsx       # Glass-box inspection panel (SQL with 1-click copy, JSON plan, time info)
│   │   │   ├── AnswerCard.tsx       # Analyst response card (verified narrative, chart/table toggle, DQ alerts)
│   │   │   ├── SuggestionChips.tsx  # Context-aware follow-up question chips
│   │   │   └── SettingsModal.tsx    # Runtime provider switcher (OpenRouter vs NVIDIA NIM)
│   │   ├── pages/
│   │   │   ├── UploadPage.tsx       # Drag-and-drop file upload, retail demo loader, schema & DQ viewer
│   │   │   ├── AnalystPage.tsx      # Interactive chat stream with query input and answer cards
│   │   │   └── DashboardPage.tsx    # Executive dashboard with KPI sparklines, charts, and anomaly alerts
│   │   ├── store/
│   │   │   └── useAppStore.ts       # Zustand state store managing datasets, sessions, chat history
│   │   ├── types/
│   │   │   └── index.ts             # TypeScript interfaces matching backend response contracts
│   │   ├── App.tsx                  # Root application component
│   │   ├── index.css                # Tailwind CSS v4 styling & dark theme tokens
│   │   └── main.tsx                 # React DOM entry point
│   ├── package.json
│   └── vite.config.ts               # Vite bundler configuration with Tailwind plugin & /api proxy
│
└── sample_data/
    ├── generate_retail.py           # Seeded generator producing retail_demo.xlsx (16.6k rows, planted drop & DQ bugs)
    └── retail_demo.xlsx             # Demo multi-sheet workbook
```

---

## 3. End-to-End Data Pipeline: Step-by-Step

### Step 1: Ingestion & Profiling (`app.ingestion.loader`, `app.profiling`)
1. Multi-sheet Excel (`.xlsx`) and CSV files are uploaded via `POST /api/datasets`.
2. Header detection runs on the first 10 rows using a $\ge 60\%$ text rule.
3. Names are sanitized to clean, unique `snake_case` (e.g. `Customer ID` $\to$ `customer_id`).
4. A DuckDB database (`data.duckdb`) is initialized, tables are loaded, and sample values are examined to cast columns into strict types (`BOOLEAN`, `BIGINT`, `DOUBLE`, `DATE`, `VARCHAR`).
5. Profiler computes null percentages, distinct ratios, quantiles, and samples. Sensitive columns matching PII keywords (`email`, `phone`, `password`, `ssn`, `pan`) have sample values suppressed.
6. Automated Data Quality rules flag:
   - Missing values
   - Duplicate rows
   - Duplicate primary IDs
   - Negative values in positive-only measures
   - Numeric outliers ($> 3 \times \text{IQR}$)
   - Inconsistent date formats
   - Orphan foreign keys

### Step 2: Semantic Layer (`app.semantic`)
1. Column roles are assigned: `id`, `time`, `measure`, `dimension`, or `text` (with `entity: true` for ranking candidates).
2. Relationships are detected by matching key names and verifying parent uniqueness ($\ge 99\%$) and child containment ($\ge 95\%$).
3. The Fact table is selected (highest row count and outgoing foreign keys, e.g. `sales`).
4. The dataset `anchor_date` is computed (the maximum date in the fact table's primary date column). Relative time expressions like *"last month"* are resolved relative to `anchor_date`.
5. Standard business metrics (`revenue`, `orders`, `units`, `return_rate`, etc.) are registered.
6. A RapidFuzz in-memory `ValueIndex` indexes unique dimension values and metric synonyms.

### Step 3: Natural Language Planning (`app.planner.planner`)
1. When a user asks a question, the question is searched against the RapidFuzz `ValueIndex` for exact matches (e.g. *"Electronics"* $\to$ `products.category = 'Electronics'`).
2. Schema, metric definitions, and recent session turns are injected into the LLM system prompt.
3. The LLM outputs a structured `PlannerOutput` JSON object:
   - `intent`: `"kpi" | "trend" | "breakdown" | "ranking" | "compare" | "why" | "dashboard"`
   - `metric`: e.g. `"revenue"`
   - `dimensions`: e.g. `["customers.region"]`
   - `time`: relative or explicit time range
   - `filters`: column comparisons
   - `comparison`: e.g. `"previous_period"`

### Step 4: Plan Validation & Intent Healing (`app.planner.validator`)
1. Verifies all metric names, table names, and column references exist in the semantic layer.
2. Heals intent discrepancies (e.g. if the question asks "why", enforces `intent: "why"` and defaults the baseline comparison).
3. If errors occur, the planner loop automatically attempts repair or returns a clear explanation.

### Step 5: Time Window Resolution (`app.planner.timeutil`)
- Translates relative expressions into half-open calendar intervals `[start, end)` anchored to `anchor_date`.
- Trailing partial periods are excluded to prevent skewed comparisons.

### Step 6: Execution Path
- **Standard Analytical Queries**:
  - `compiler.py` converts the plan into parameterized DuckDB SQL using single-scan `FILTER (WHERE ...)` conditional aggregation and deduplicated joins.
  - `executor.py` runs the query on a read-only DuckDB connection protected by a 20-second watchdog timer.
- **Why / Root-Cause Queries**:
  - `why_engine.py` executes period-over-period delta decomposition across candidate dimensions.
  - Invariant $\sum \delta_s = \Delta$ is enforced by preserving missing values in a `(missing)` bucket.
  - Identifies top driver segments where contribution $\ge 30\%$ and lift $\ge 1.5$.
  - Recursively drills down into underlying entities (e.g. specific products causing the category decline).

### Step 7: Visualization Selection (`app.viz.selector`)
Maps the result shape deterministically to an optimal chart specification:
- Single scalar $\to$ **KPI Card** with delta badge
- Time grain + measure $\to$ **Line Chart** with gradient fill
- Categorical dimension $\to$ **Vertical Bar** ($\le 12$ items) or **Horizontal Bar**
- Period comparison $\to$ **Grouped Bar** (Current vs Baseline)
- Why analysis $\to$ **Signed Contribution Bar** (diverging red/green waterfall)
- Multi-dimensional data $\to$ **Interactive Table**

### Step 8: Narration & Number Verification (`app.narrator`)
1. Aggregates and derived totals are passed to the LLM to compose 2–4 concise sentences.
2. `verify.py` scans the narrative with regex and verifies that every stated number exists in the DuckDB result.
3. If all numbers match, the narrative is certified with the `✓ DuckDB Verified` badge. If verification fails, a deterministic templated narrative is substituted.

---

## 4. Multi-Provider LLM Fallback System (`app.llm.client`)

RootCause implements a transparent dual-provider fallback mechanism:
- **Primary Provider**: OpenRouter (`nex-agi/nex-n2.5-mini:free` or free models).
- **Secondary Provider**: NVIDIA NIM (`meta/llama-3.2-11b-vision-instruct`).
- **Failover Logic**:
  1. Requests attempt the configured active provider.
  2. If the active provider returns HTTP 429 (rate limit), timeout, or invalid JSON, the client automatically executes the request on the fallback provider.
  3. Runtime switching is supported via the UI Settings modal or `POST /api/settings`.

---

## 5. Running the Application

### Start the Backend Server:
```bash
cd backend
../.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Start the Frontend Development Server:
```bash
cd frontend
npm run dev
```
Open your browser at `http://localhost:5173`.

### Run Automated Backend Tests:
```bash
PYTHONPATH=backend .venv/bin/pytest backend/tests/ -v
```
All 7 unit and integration test suites will execute and validate:
- Ingestion & profiling
- Column role tagging and join detection
- Plan-to-SQL compiler
- Period-over-period Why engine decomposition
- Number verifier and fallback generator
- FastAPI REST endpoints
