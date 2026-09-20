# demo-script.md: Live Demo (about 6-7 minutes)

Goal: show, in order, every item of the expected demonstration and make the judging criteria visible. Data: `sample_data/retail_demo.xlsx` (data ends 2026-08-31, so "last month" = August 2026).

## 0. Pre-demo checklist (30 min before)
- [ ] Backend and frontend running; `.env` has a valid `LLM_API_KEY`; internet checked.
- [ ] Dataset uploaded once and the dashboard generated once (cache warm); a fresh session created.
- [ ] Browser zoom 100-110%, notifications off, a second tab with a backup screen recording.
- [ ] Run the live evaluation (`test-cases.md` section 4) once; nothing red.
- [ ] Sample data button works as a fallback if file upload misbehaves.
- [ ] Decide who speaks and who drives.

## 1. Hook (30 s)
"Dashboards answer the questions someone thought of in advance. Our product answers the question you have right now, on your own Excel, without SQL. The AI plans the analysis; a data engine computes it, so every number comes from your actual data."

## 2. Upload and understanding (60 s)
Action: drop `retail_demo.xlsx` (5 sheets).
Show: tables and row counts; roles (time, measure, dimension); **relationships** detected automatically (sales → customers, products); **data-quality report** (missing regions, duplicate rows, negative quantities, mixed date formats, orphan product ids) with impact statements.
Say: "We found these issues before anyone trusted a number, and each one is tied to the answers it affects."
Criteria: Data Understanding, Data Quality.

## 3. One-prompt dashboard (60 s)
Ask: "Analyse this dataset and create a management dashboard showing our current business performance."
Show: KPI cards with change versus last month, trend, breakdowns, top products, alerts (revenue drop, low stock, data quality), executive summary.
Say: "Nobody built this report; it was generated from the data."
Criteria: Visualisation, User Experience.

## 4. "Why?" drill-down (90 s)
1. Click the revenue-drop alert or ask: "Why did revenue fall last month?" → contribution chart and drill path (Electronics → West), explanation with shares.
2. Ask: "Was it mainly because of a particular product category?" → confirms Electronics.
3. Ask: "Show me the five products responsible for the largest decline." → horizontal bar of five Electronics products.
Say: "This is contribution analysis computed in the engine, not guessed by the model."
Criteria: Drill-Down, Correctness.

## 5. Conversational follow-up (60 s)
Ask in sequence: "Show revenue by region." → "Only the last six months." → "Compare it with the previous six months." → "Which region contributed most to the decline?"
Show: the "Current analysis" chips change with each turn; the data-quality banner on the region breakdown ("3% of customers have no region ...").
Say: "Each follow-up patches the previous plan; the user never rebuilds a report."
Criteria: Follow-Up Analysis, Data Quality.

## 6. Glass box (60 s)
Open "How this was calculated" on one answer: structured plan, assumptions, resolved date range, SQL.
Say: "The model never sees your rows and does no math. It produces this plan; we validate it against the schema, compile it to SQL, and run it in DuckDB. The narrative's numbers are verified against the result table."
Criteria: Technical Depth, Correctness.

## 7. Wrap (30 s)
Optional: upload a second dataset (Superstore) live to show it is not tied to the demo file, only if it has been tested.
Close: "An analyst on demand for people who own the data but can't query it."

## 8. If something goes wrong
| Problem | Response |
|---|---|
| LLM slow or down | Switch to the backup screen recording; mention the 30 s timeout and friendly error handling |
| A question gives an odd answer | Open the plan; point out the assumption; rephrase once; do not debug live |
| Upload fails | "Use sample data" button |
| Dashboard slow | Use the pre-generated (cached) dashboard |
| Wi-Fi fails | Local backup recording plus screenshots in `docs/backup/` |

## 9. Likely judge questions and short answers
- **Do you send our data to the LLM?** No. It receives schema, column descriptions, at most 5 sample values per column (configurable, and suppressed for sensitive-looking columns), the question, and aggregated results for wording. Never raw tables.
- **How do you know the numbers are right?** SQL runs in DuckDB on the actual data; tests compare with independent pandas results; the narrative's numbers are checked against the result table; plan and SQL are inspectable.
- **What if the LLM writes a wrong plan?** A validator checks it against the semantic layer; assumptions are shown; one repair attempt; otherwise a clarification.
- **How does "Why" work?** Period-over-period delta decomposed across all dimensions; drivers require a large share and lift; recursive drill; the parts always sum to the total change.
- **What about messy data?** Type and date inference, quality checks with quantified impact, `(missing)` buckets so nothing is silently dropped.
- **What are the limits?** One fact table per question, no forecasting, non-additive metrics are not decomposed, relationships need matching names and unique parent keys. Documented in the README.
- **Scale?** DuckDB handles millions of rows locally; the demo is tuned for tens of thousands.

## 10. Roles and timing
| Segment | Time | Speaker |
|---|---|---|
| Hook and wrap | 1:00 | TBD |
| Upload, dashboard | 2:00 | TBD |
| Why, follow-up, glass box | 3:30 | TBD |
Rehearse twice end to end (`implementation.md` step 8.5); time it; cut segment 7 if over.
