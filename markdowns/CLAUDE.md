# CLAUDE.md

Project: **AskData** (working name) is an AI-powered data analyst for the 24-hour hackathon problem "From Static Dashboards to an AI-Powered Data Analyst".
Users upload Excel/CSV data, ask questions in plain language, and get charts, KPIs, tables, dashboards and "why" explanations. Every number is computed on the actual data by a deterministic engine. The LLM only plans and narrates.

## Read first
- `plan.md`: users, scope (P0/P1/P2), timeline, risks
- `architecture.md`: components, plan schema, API contract, folder layout
- `implementation.md`: ordered build steps with "done when" criteria. Follow this order.
- `progress.md`: live status. Update it after every completed task.

## Non-negotiable rules
1. **The LLM never does math and never sees the full dataset.** It turns a question into a structured query plan and turns aggregated results into words. All numbers come from DuckDB.
2. **Data allowed to reach the LLM:** table/column names, types, roles, descriptions; at most 5 sample values per column (disable with `SEND_SAMPLES=false`); value-index matches for terms in the question; the current query plan; aggregated result rows (at most `NARRATOR_MAX_ROWS`); data-quality flags. Never raw table rows.
3. **Structured output only.** The planner returns JSON that is parsed into Pydantic models and validated against the semantic layer. Free-form model-written SQL runs only through the guarded fallback (`planner/fallback_sql.py`).
4. **SQL safety.** Identifiers come only from the validated schema and are always double-quoted. User values are bound as parameters, never string-interpolated. Fallback SQL must be a single SELECT, checked with sqlglot (table whitelist, no table functions), run on a read-only connection with a row cap and a timeout.
5. **Time is anchored to the data, not the clock.** "Last month" and "last 6 months" resolve against `anchor_date` (the max date of the primary date column). Always show the resolved date range in the UI.
6. **Every answer returns** `plan`, `sql`, `result`, `chart`, `narrative`, `dq_warnings` (see `architecture.md` section 10). The user can always inspect the plan and SQL.
7. **Narration is verified.** Every number in the narrative must match the result table (allowing rounding and formatting). If verification still fails after one retry, use the templated summary.
8. **Nothing is silently dropped.** Rows excluded (nulls, unparseable dates) are counted and shown. Null dimension values form a `(missing)` bucket so breakdowns and contributions still sum to the total.
9. **Fail visibly.** If a question is ambiguous or unsupported, say why and offer alternatives. Never invent a column, metric or number.
10. **Why/drill-down decomposes additive metrics only** (sum, count). For ratio or average metrics, decompose numerator and denominator separately, or say it is unsupported for that metric.

## Stack
- Backend: Python 3.11+, FastAPI, Uvicorn, DuckDB, pandas + openpyxl (ingestion only), Pydantic v2, sqlglot, rapidfuzz, python-multipart, python-dotenv, pytest, httpx.
- LLM: provider hidden behind `backend/app/llm/client.py` (default: Anthropic Claude API via the `anthropic` SDK, tool use for structured output). Changing providers must only touch that file.
- Frontend: React + Vite + TypeScript, Tailwind CSS, ECharts (`echarts-for-react`), zustand. Node 20+.

Full folder layout: `architecture.md` section 13. Top level: `backend/`, `frontend/`, `sample_data/`, and the root `.md` files.

## Commands
Backend (run from `backend/`):
```
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # then fill in LLM_API_KEY
uvicorn app.main:app --reload --port 8000
pytest -q
```
Frontend (run from `frontend/`):
```
npm install
npm run dev                        # http://localhost:5173, proxies /api to :8000
```
Sample data (run from repo root):
```
python sample_data/generate_retail.py    # writes sample_data/retail_demo.xlsx
```

## Environment variables (`backend/.env`)
| Name | Default | Meaning |
|---|---|---|
| `LLM_API_KEY` | none | provider API key |
| `LLM_MODEL` | provider default | model id used for planner, narrator, enrichment |
| `SEND_SAMPLES` | `true` | allow up to 5 sample values per column in prompts |
| `DATA_DIR` | `backend/data` | datasets, sessions, logs (gitignored) |
| `MAX_RESULT_ROWS` | `1000` | row cap returned to the frontend |
| `NARRATOR_MAX_ROWS` | `50` | row cap sent to the narrator |
| `QUERY_TIMEOUT_S` | `20` | per-query timeout |

## Conventions
- Type hints everywhere. Pydantic models for all data passed between modules. Use `logging`, not `print`.
- One responsibility per module, as laid out in `architecture.md`. LLM calls happen only through `llm/client.py`, and only from the planner, narrator, enrichment and dashboard-planning modules.
- DuckDB tables and columns are snake_case (`sales.order_date`). Original names are kept as `display_name` for the UI.
- Prompts live in `backend/app/llm/prompts/` as files, not inline strings.
- Every module gets pytest tests. Compiler and why-engine tests compare against independent pandas computations on the sample data.
- API errors return `{status, message}`. Never return a raw stack trace; log details server-side.
- Frontend consumes the response contract in `architecture.md` section 10 exactly. Types in `frontend/src/types.ts` mirror the backend models.
- Commit small and often.

## Definition of done (per task)
Code written, tests pass, checkbox ticked in `progress.md`, and a decision logged if the plan schema, API contract or scope changed.

## Working agreement for Claude Code
- Follow the order in `implementation.md`. Do not start a later phase until the current one is done or blocked.
- Do not add features outside P0/P1 in `plan.md` without asking.
- Ask before changing the query plan schema or the API contract; both ripple across backend, frontend and prompts.
- Update `progress.md` as you go (tasks, blockers, decisions).
- If a requirement is unclear, re-read `plan.md` section 1 (problem summary) before guessing.
