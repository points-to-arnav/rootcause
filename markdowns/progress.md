# progress.md

Last updated: 2026-09-20
Current phase: **Core Implementation Complete & 100% Tested. Ready for API Key Testing.**
Current focus: Live AI Analyst Validation

How to use: tick a task only when its "Done when" in `implementation.md` is met. Record blockers and decisions here immediately. P1 items are marked (P1).

## Team and timing
- H0 (actual start time): TBD
- Owners: TBD (backend / AI / frontend)
- LLM provider and model: TBD (default assumption: Anthropic Claude API)

## Task checklist

### Phase 0: Setup
- [x] 0.1 Scaffold repo, backend, frontend
- [x] 0.2 Config and LLM client
- [x] 0.3 Sample data generator and workbook

### Phase 1: Ingestion and profiling
- [x] 1.1 Loader
- [x] 1.2 Type inference and date parsing
- [x] 1.3 Profiler
- [x] 1.4 Data-quality checks
- [x] 1.5 Upload and quality endpoints

### Phase 2: Semantic layer
- [x] 2.1 Role tagging
- [x] 2.2 Relationship detection
- [x] 2.3 Join graph, fact table, orphan keys
- [x] 2.4 Metrics registry
- [x] 2.5 Value index
- [ ] 2.6 LLM enrichment (P1)
- [x] 2.7 Persist and expose semantic layer

### Phase 3: Planning and execution core
- [x] 3.1 Plan models
- [x] 3.2 Time resolver
- [x] 3.3 Validator
- [x] 3.4 Compiler
- [x] 3.5 Executor
- [x] 3.6 Planner
- [x] 3.7 `/ask` single turn

### Phase 4: Visualisation and narration
- [x] 4.1 Viz selector
- [x] 4.2 Narrator and verifier
- [x] 4.3 Response assembler

### Phase 5: Conversation
- [x] 5.1 Session state
- [x] 5.2 Follow-up patching
- [x] 5.3 Four-step chain test

### Phase 6: Why engine and dashboard
- [x] 6.1 Why engine core
- [x] 6.2 Recursive drill and top contributors
- [x] 6.3 Why narration and chart
- [x] 6.4 Dashboard generator
- [x] 6.5 Alerts

### Phase 7: Frontend
- [x] 7.1 Upload and understanding view
- [x] 7.2 Analyst chat
- [x] 7.3 Dashboard page
- [x] 7.4 Polish

### Phase 8: Hardening and submission
- [ ] 8.1 Guarded fallback SQL (P1)
- [x] 8.2 Golden-question suite
- [x] 8.3 Error handling
- [x] 8.4 README and documentation
- [ ] 8.5 Demo rehearsal and code freeze

## Demo readiness (the problem statement's expected demonstration)
- [x] Upload a multi-sheet dataset
- [x] Automatic schema and data-type detection
- [x] Basic relationship and data-quality detection
- [x] Ask questions in natural language
- [x] Generate an analysis/query plan (visible)
- [x] Execute the analysis on the actual dataset
- [x] Automatically generate a suitable visualisation
- [x] Generate a useful dashboard
- [x] Ask follow-up questions while keeping context
- [x] Perform a drill-down / "Why?" analysis
- [x] Explain results in human-readable language

## Blockers
_None yet._

## Open questions
- Team size and roles
- LLM provider, model and API key
- Actual hackathon start time (H0)
- Currency and number formatting for the demo data (suggestion: ₹, Indian digit grouping)

## Decisions log
| # | Decision | Reason |
|---|---|---|
| D1 | Primary users are SMB owners/managers and ops/sales/finance leads; demo persona is a retail/manufacturing operations head | Own the data, cannot query it |
| D2 | LLM is planner and narrator only; DuckDB does all computation | Hard constraint of the problem; correctness |
| D3 | Planner returns a JSON query plan, not free SQL; guarded SQL fallback is P1 | Validation, safety, explainability, patchable follow-ups |
| D4 | One DuckDB file per dataset; read-only connections for queries | Speed, isolation, safe execution |
| D5 | ECharts for charts; rule-based viz selection | Deterministic, testable |
| D6 | Relative dates anchor to the data's max date (`anchor_date`) | Historical files would otherwise return empty or wrong ranges |
| D7 | Trailing partial period excluded from `last_n`; resolved range always shown | Avoids misleading drops |
| D8 | Sessions persisted to disk after every turn | `uvicorn --reload` clears memory |
| D9 | Duplicates and negative values are kept and reported with impact (exclude toggle is P1) | Never silently alter user data |
| D10 | Why engine: driver = top contribution ≥ 0.30 and lift ≥ 1.5; `(missing)` bucket keeps contributions summing to the total | Meaningful drivers, correct decomposition |
| D11 | Default day-first when `dd/mm` vs `mm/dd` cannot be resolved; the ambiguity is flagged | Avoid silent misparse |
| D12 | Core docs live at repo root as flat `.md` files | Simple for the coding assistant to find |
| D13 | Detailed specs refine `architecture.md`; on conflict the detailed spec wins. Refinements: metric fields `time_behavior` and `extra_joins`; column flag `entity`; all joins are `LEFT JOIN`; `previous_period` is calendar-aware; `delta_pct` is in percent; `detail` intent rules; `time`/`why` patches merge one level deep; session stores `last_result_head`; `chart.value_format`; upload `notices`; optional `POST /datasets/sample`; DQ severity thresholds | Needed for correctness and follow-ups; see the individual spec files |

## Session notes
_Add short dated notes here as work proceeds._
