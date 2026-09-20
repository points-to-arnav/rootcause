# AskData

An AI-powered data analyst. Upload Excel or CSV files, ask questions in plain language, and get charts, KPIs, tables, dashboards and "why did this change?" explanations, all calculated on your actual data.

Built for the 24-hour hackathon problem *From Static Dashboards to an AI-Powered Data Analyst*.

> Status: replace this line with the final status and team names before submission.

## What it does
1. **Understands your data:** detects tables, column types, dates, measures and categories, relationships between tables, and data-quality problems (missing values, duplicates, negative or unusual values, inconsistent dates).
2. **Answers questions:** "Show me monthly revenue for 2026", "Top 10 products", "Revenue by region for the last six months".
3. **Chooses the visualisation:** KPI, line, bar, horizontal bar or table, depending on the shape of the result.
4. **Builds a dashboard in one prompt:** KPIs, trends, breakdowns, rankings and alerts.
5. **Remembers the conversation:** "Only the last six months." → "Compare it with the previous six months." → "Which region contributed most to the decline?"
6. **Explains changes:** "Why did revenue fall?" decomposes the change across regions, categories and other dimensions and drills down to the biggest contributors.
7. **Shows its work:** every answer includes the analysis plan, the SQL, assumptions and the data-quality warnings that affect it.

## How the AI reaches the data
The full dataset is never sent to an LLM. The model is a planner and narrator; a deterministic engine does all calculations.

```
Excel/CSV → DuckDB tables → profiler + data-quality checks → semantic layer
                                                    │
Question + conversation state → LLM planner → structured query plan (JSON)
   → validator → SQL compiler → DuckDB (read-only) → result table
   → chart selection (rules) + LLM narrator (aggregates only, numbers verified)
   → answer: chart · explanation · plan · SQL · data-quality warnings
```
- **Semantic layer:** column roles, join graph, metric definitions, value index for resolving terms like "electronics".
- **Query plan:** intent, metric, dimensions, filters, time range, comparison. Follow-ups are patches to the plan.
- **Why engine:** deterministic contribution and lift analysis, with recursive drill-down.
- **Data sent to the LLM:** schema and column descriptions, at most 5 sample values per column (can be disabled; skipped for sensitive-looking columns), the question, the current plan, and aggregated results. Never raw rows.

Details: `architecture.md`, `data-engine.md`, `semantic-layer.md`, `query-plan-spec.md`, `analysis-modules.md`.

## Supported data
| Format | Support |
|---|---|
| `.xlsx` (multiple sheets, each becomes a table) | yes |
| `.csv` (multiple files; encodings UTF-8/Latin-1; delimiters comma, semicolon, tab, pipe) | yes |
| `.xls`, `.tsv` | best effort (optional) |
| Database connections | not included |

Limits: one fact table per question; no forecasting; ratio metrics (e.g. average order value) are not decomposed in "why" analysis; relationships require matching key names and a unique parent key; merged cells and multi-row headers are not handled. Default upload limit 100 MB per file.

## Quick start
Requirements: Python 3.11+, Node 20+, an LLM API key.

```
# Backend (from backend/)
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # set LLM_API_KEY (and LLM_MODEL if needed)
uvicorn app.main:app --reload --port 8000

# Frontend (from frontend/)
npm install
npm run dev                        # http://localhost:5173

# Sample data (from repo root)
python sample_data/generate_retail.py
```
Open http://localhost:5173, click "Use sample data" (or drop `sample_data/retail_demo.xlsx`), and ask: *"Analyse this dataset and create a management dashboard."*

## Configuration (`backend/.env`)
| Variable | Default | Meaning |
|---|---|---|
| `LLM_API_KEY` | none | LLM provider key |
| `LLM_MODEL` | provider default | model used for planning and narration |
| `SEND_SAMPLES` | `true` | send up to 5 sample values per column to the LLM |
| `DATA_DIR` | `backend/data` | storage for datasets and sessions |
| `MAX_RESULT_ROWS` | `1000` | max rows returned per query |
| `NARRATOR_MAX_ROWS` | `50` | max aggregated rows sent to the narrator |
| `QUERY_TIMEOUT_S` | `20` | per-query timeout |

## Example questions
- What is our total revenue? / How many orders did we have last month?
- Show me monthly revenue for 2026.
- Revenue by category for the last 6 months.
- Top 10 products by revenue in the West.
- Why did revenue fall last month? → Was it mainly a particular product category? → Show me the five products responsible for the largest decline.
- Show revenue by region. → Only the last six months. → Compare it with the previous six months. → Which region contributed most to the decline?

## Project structure
```
backend/app/   ingestion · profiling · semantic · planner · memory · analysis · viz · narrator · llm · api
backend/tests/ pytest suite (offline with recorded LLM outputs; live evaluation script)
frontend/src/ pages · components · store · api client
sample_data/   generator and demo workbook
*.md           project documentation
```

## Testing
```
cd backend && pytest -q
```
Results are checked against independent pandas calculations on the sample workbook. See `test-cases.md`.

## Documentation index
`plan.md` · `architecture.md` · `implementation.md` · `progress.md` · `data-engine.md` · `semantic-layer.md` · `query-plan-spec.md` · `conversation-memory.md` · `analysis-modules.md` · `prompts.md` · `api-spec.md` · `frontend.md` · `viz-rules.md` · `test-cases.md` · `demo-script.md`

## Team
TBD
