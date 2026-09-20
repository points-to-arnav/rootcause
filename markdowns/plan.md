# plan.md: AskData

## 1. Problem summary
Hackathon problem: **"From Static Dashboards to an AI-Powered Data Analyst"** (24 hours).
Core loop: **Upload data → Understand it → Ask a question → Analyse the actual data → Visualise and explain the result.**

Hard constraint: the complete dataset must not simply be sent to an LLM. The AI understands the question and decides what to analyse; a reliable data engine performs the calculation.

Deliverables required:
1. **Platform:** working web interface with data upload and understanding, natural-language analysis, dynamic visualisation, conversational follow-up.
2. **Data engine / AI:** schema and metadata handling, query/analysis generation, execution against the actual data, result explanation.
3. **Documentation:** system architecture, supported data formats, a brief explanation of the AI-to-data workflow (delivered as `README.md`).

Expected demonstration: multi-sheet upload; automatic schema and type detection; relationship and data-quality detection; natural-language questions; a visible analysis/query plan; execution on the real data; automatic visualisation; a generated dashboard; follow-up questions with context; a "Why?" drill-down; human-readable explanations.

## 2. Users
**Primary (build for these)**
- **Business owners and managers at small/medium businesses.** They hold Excel/CSV exports, have no analyst, and ask ad-hoc questions ("why did revenue fall?").
- **Operations, sales and finance leads in mid-size companies.** They depend on an analyst or IT for every new report.

**Secondary (mention in the pitch, do not build for them)**
- Data analysts: use it for a fast first-pass answer or a draft dashboard.
- Executives: consume the auto-generated dashboard.

**Demo persona:** head of operations at a retail/manufacturing company. Uploads a workbook with Sales, Customers, Products, Inventory and Returns, and needs answers without waiting for a report.

## 3. Value proposition
"An analyst on demand for people who own the data but can't query it."
1. Raw files become instant understanding: schema, relationships, data-quality issues.
2. New questions get answered without waiting for an analyst or a new report.
3. It explains *why* a number changed, not just what it is.
4. One prompt generates a management dashboard.
5. Data problems are flagged before the user trusts a wrong number.

## 4. Scope
### P0: must work in the demo
- Upload `.xlsx` (multiple sheets) and `.csv` (multiple files) into one dataset.
- Automatic table, column, data-type, date, measure/dimension detection; missing values, duplicates.
- Relationship detection between tables (e.g. `sales.customer_id` → `customers.customer_id`).
- Data-quality report: missing values, duplicate IDs, negative/unusual values, inconsistent date formats, orphan keys, with a plain-language impact statement.
- Natural-language questions → structured query plan → SQL on DuckDB → result.
- Automatic chart selection (KPI, line, bar, horizontal bar, table).
- One-prompt management dashboard (KPIs, trends, rankings, breakdowns, alerts).
- Conversational follow-up (plan patching).
- "Why?" drill-down with contribution analysis.
- Human-readable narrative with verified numbers.
- Visible plan and SQL for every answer; data-quality warnings attached to affected answers.

### P1: if time allows (cut in this order when behind: 2.6, 8.1, suggestion chips, semantic editing)
- LLM enrichment of column descriptions and metric synonyms (2.6).
- Guarded LLM-SQL fallback with repair loop (8.1).
- Follow-up suggestion chips.
- User editing of semantic layer (confirm/reject relationships, rename metrics).
- Exclude-duplicates toggle.
- Temporal localisation in Why (which weeks drove the change).
- Trend comparison overlay (previous period as a second line).
- `.xls` / `.tsv` support.

### P2: stretch
- Price / volume / mix decomposition.
- Structured database connection (Postgres/MySQL).
- Export dashboard (PDF/PNG).

### Non-goals
Authentication, multi-tenancy, forecasting, real-time streaming data, editing the user's data.

## 5. How we address the judging criteria
| Criterion | How we address it | Where |
|---|---|---|
| Data Understanding | Type/date inference, role tagging, relationship detection, join graph, value index | Phases 1-2 |
| Natural-Language Analysis | Schema-aware planner returning a validated JSON plan; value retrieval for filters | Phase 3 |
| Correctness | Deterministic SQL from DuckDB; tests against independent pandas results; verified narration | Phases 3-4 |
| Visualisation | Rule-based chart selection from result shape; ECharts | Phase 4, 7 |
| Follow-Up Analysis | Session state = current plan; follow-ups are patches | Phase 5 |
| Drill-Down | Contribution and lift analysis across dimensions, recursive drill path | Phase 6 |
| Data Quality | Profiler checks, impact statements, warnings tied to each answer | Phases 1, 4 |
| User Experience | Glass-box view (plan/SQL/assumptions), suggestion chips, clear errors | Phase 7 |
| Technical Depth | Semantic layer, plan→SQL compiler, why engine, number verification | All |

## 6. Demo dataset and storyline
A synthetic **Retail Ops** workbook, `sample_data/retail_demo.xlsx`, generated by `sample_data/generate_retail.py` (seed 42). Data covers 2025-01-01 to 2026-08-31, so "last month" = August 2026.

| Sheet | Columns | Approx. size |
|---|---|---|
| Sales | order_id, order_date, customer_id, product_id, quantity, unit_price, discount_pct, amount | 18,000 rows |
| Customers | customer_id, customer_name, region (North/South/East/West), customer_type (Retail/Wholesale/Corporate), signup_date | 800 rows |
| Products | product_id, product_name, category (Electronics/Home/Apparel/Grocery/Sports), sub_category, unit_cost, list_price | 120 rows |
| Inventory | product_id, snapshot_date (month-end), warehouse_region, stock_on_hand, reorder_level | one row per product per region per month-end |
| Returns | return_id, order_id, return_date, reason, refund_amount | about 4% of orders |

Planted patterns:
1. Mild growth trend plus seasonality, so history looks realistic.
2. **August 2026:** Electronics revenue in the West region falls about 75% versus July (stock-out; Inventory shows `stock_on_hand = 0` for its top products in West at August month-end). Total revenue falls roughly 15-20% month over month. The five products with the largest decline are all Electronics.
3. Data-quality issues: about 3% of Customers with missing region; about 30 duplicated Sales rows (same order_id); about 20 negative quantities; about 2% of `order_date` values stored as text in `dd/mm/yyyy` while the rest are real dates; a few outlier amounts (about 10x typical); about 10 Sales rows whose product_id is not in Products.

Demo storyline:
1. Upload the workbook → show tables, detected relationships, data-quality report.
2. "Create a management dashboard showing our current business performance."
3. "Why did revenue fall last month?" → "Was it mainly because of a particular product category?" → "Show me the five products responsible for the largest decline."
4. Follow-up chain: "Show revenue by region." → "Only the last six months." → "Compare it with the previous six months." → "Which region contributed most to the decline?"
5. Open the plan/SQL viewer on one answer; show a data-quality warning attached to an answer.

## 7. Timeline (24 h; set H0 to the real start and shift blocks)
| Block | Hours | Focus | Phases (`implementation.md`) | Exit criterion |
|---|---|---|---|---|
| A | H0-1 | Setup, sample data, LLM client | 0 | Both servers run; sample workbook generated |
| B | H1-5 | Ingestion, profiling, DQ, semantic layer | 1-2 | Upload shows schema, relationships, DQ report |
| C | H5-9 | Planner, validator, compiler, `/ask` | 3 | Simple questions answered correctly on real data |
| D | H9-12 | Viz, narrator, response assembly; frontend shell in parallel | 4, 7.1-7.2 | Chat with charts works end to end |
| E | H12-15 | Conversation follow-ups | 5 | Four-step follow-up chain passes |
| F | H15-19 | Why engine, dashboard, alerts | 6 | Demo storyline works end to end |
| G | H19-22 | Frontend polish, fallback SQL, hardening | 7.3-7.4, 8.1-8.3 | No crashes on golden questions |
| H | H22-24 | README, diagram, rehearsal, code freeze | 8.4-8.5 | Freeze at H23; backup screen recording made |

With two or more people, one person takes the frontend (Phase 7) from block C onward, working against mocked responses that follow the contract in `architecture.md` section 10.

## 8. Risks and mitigations
| Risk | Mitigation |
|---|---|
| LLM produces a wrong plan (wrong column or metric) | Validator against semantic layer; assumptions shown in UI; one repair call; golden-question tests |
| Join fan-out inflates numbers | Fact→dimension joins only; dimension keys deduplicated in a CTE; tests against pandas |
| Messy Excel (header not in row 1, merged cells, total rows) | Header-row heuristic; document unsupported layouts; demo file is realistic but parseable |
| Date ambiguity (`dd/mm` vs `mm/dd`) | Infer from unambiguous rows; flag if unresolved |
| False relationships | Name/type compatibility, containment ≥ 0.95, unique parent key, confidence shown |
| Why engine misleads when segments offset | Signed contributions; explicit "offsetting" flag; lift threshold |
| LLM latency or rate limits | Two LLM calls per question; timeouts and retries; dashboard cached; warm up before demo |
| Scope creep | P0/P1/P2 list and cut order above |
| Live demo failure | Backup screen recording at H22; pre-loaded dataset session |

## 9. Open decisions (record answers in `progress.md`)
- Team size and who owns backend / AI / frontend.
- LLM provider, model and API key (default assumption: Anthropic Claude API).
- Actual hackathon start time (H0).
- Currency and number formatting for the demo dataset (suggestion: ₹ with Indian digit grouping).
