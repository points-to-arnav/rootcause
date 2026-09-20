# progress.md

Last updated: 2026-09-20
Current phase: **Planning complete. Build not started.**
Current focus: Phase 0 (setup)

How to use: tick a task only when its "Done when" in `implementation.md` is met. Record blockers and decisions here immediately. P1 items are marked (P1).

## Team and timing
- H0 (actual start time): TBD
- Owners: TBD (backend / AI / frontend)
- LLM provider and model: TBD (default assumption: Anthropic Claude API)

## Task checklist

### Phase 0: Setup
- [ ] 0.1 Scaffold repo, backend, frontend
- [ ] 0.2 Config and LLM client
- [ ] 0.3 Sample data generator and workbook

### Phase 1: Ingestion and profiling
- [ ] 1.1 Loader
- [ ] 1.2 Type inference and date parsing
- [ ] 1.3 Profiler
- [ ] 1.4 Data-quality checks
- [ ] 1.5 Upload and quality endpoints

### Phase 2: Semantic layer
- [ ] 2.1 Role tagging
- [ ] 2.2 Relationship detection
- [ ] 2.3 Join graph, fact table, orphan keys
- [ ] 2.4 Metrics registry
- [ ] 2.5 Value index
- [ ] 2.6 LLM enrichment (P1)
- [ ] 2.7 Persist and expose semantic layer

### Phase 3: Planning and execution core
- [ ] 3.1 Plan models
- [ ] 3.2 Time resolver
- [ ] 3.3 Validator
- [ ] 3.4 Compiler
- [ ] 3.5 Executor
- [ ] 3.6 Planner
- [ ] 3.7 `/ask` single turn

### Phase 4: Visualisation and narration
- [ ] 4.1 Viz selector
- [ ] 4.2 Narrator and verifier
- [ ] 4.3 Response assembler

### Phase 5: Conversation
- [ ] 5.1 Session state
- [ ] 5.2 Follow-up patching
- [ ] 5.3 Four-step chain test

### Phase 6: Why engine and dashboard
- [ ] 6.1 Why engine core
- [ ] 6.2 Recursive drill and top contributors
- [ ] 6.3 Why narration and chart
- [ ] 6.4 Dashboard generator
- [ ] 6.5 Alerts

### Phase 7: Frontend
- [ ] 7.1 Upload and understanding view
- [ ] 7.2 Analyst chat
- [ ] 7.3 Dashboard page
- [ ] 7.4 Polish

### Phase 8: Hardening and submission
- [ ] 8.1 Guarded fallback SQL (P1)
- [ ] 8.2 Golden-question suite
- [ ] 8.3 Error handling
- [ ] 8.4 README and documentation
- [ ] 8.5 Demo rehearsal and code freeze

## Demo readiness (the problem statement's expected demonstration)
- [ ] Upload a multi-sheet dataset
- [ ] Automatic schema and data-type detection
- [ ] Basic relationship and data-quality detection
- [ ] Ask questions in natural language
- [ ] Generate an analysis/query plan (visible)
- [ ] Execute the analysis on the actual dataset
- [ ] Automatically generate a suitable visualisation
- [ ] Generate a useful dashboard
- [ ] Ask follow-up questions while keeping context
- [ ] Perform a drill-down / "Why?" analysis
- [ ] Explain results in human-readable language

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
