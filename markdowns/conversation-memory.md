# conversation-memory.md: Session State and Follow-Up Patching

Goal: users continue an analysis ("Only the last six months." → "Compare it with the previous six months." → "Which region contributed most to the decline?") without repeating context. The state is the current query plan; a follow-up is a patch to it.

Refinements to `architecture.md` sections 5 and 11: the merge is one level deep for `time` and `why`; session state also stores `last_result_head`.

## 1. Session state (`memory/session.py`)
```json
{
  "session_id": "s_9f3a",
  "dataset_id": "ds_ab12cd34",
  "created_at": "2026-09-20T12:10:00+05:30",
  "current_plan": {},
  "last_result_head": {"columns": ["region", "revenue"], "rows": [["West", 1250000]]},
  "history": [
    {"turn": 1, "question": "Show revenue by region.", "plan": {},
     "summary": "Revenue by region, all time; West is largest.",
     "timestamp": "2026-09-20T12:10:05+05:30"}
  ]
}
```
- `history` keeps the last 20 turns. The planner receives `current_plan`, the last 3 turns (question and one-line summary), and `last_result_head`.
- `last_result_head` holds at most 5 aggregated rows of the latest result. It lets the planner resolve references such as "that region", "the top one", "the second product".
- Persisted to `DATA_DIR/{dataset_id}/sessions/{sid}.json` after every turn and reloaded on start (dev auto-reload clears memory).
- One request at a time per session (a per-session lock); a second request waits or returns HTTP 409.

## 2. Planner contract for follow-ups
The planner sets `is_follow_up: true` when the question builds on the current plan, and returns `changes` (a partial plan). For a self-contained new question it returns `is_follow_up: false` and a full `plan`, which replaces `current_plan`. When unsure, prefer follow-up only if the question lacks a metric or subject of its own or contains reference words (it, that, those, only, also, same, instead, now, drill, compare it).

## 3. Merge rules (`memory/patcher.py`, deterministic)
Applied to `current_plan` with `changes`:
1. **Top-level fields** (`intent`, `metric`, `dimensions`, `sort`, `limit`, `comparison`): present in `changes` → replace. Explicit `null` → clear (for `dimensions`, set `[]`).
2. **`time` and `why` merge one level deep:** each sub-field present in `changes.time` (`column`, `range`, `grain`) replaces that sub-field; `null` clears it. Same for `why.dimensions` and `why.max_depth`. This keeps the grain when only the range changes.
3. **Filters:** `filters_add` appends; a filter with the same `column` and `op` replaces the existing one. `filters_remove` is a list of columns whose filters are removed. `filters` (full replacement) is honoured if present.
4. **Intent change:** after merging, fields invalid for the new intent are dropped (e.g. `limit` and `dimensions` for `kpi`, `comparison` for `trend`); required fields are filled from context when possible (e.g. `why` gets `time.range` from the current plan).
5. **Re-validate** the merged plan; on errors, one repair call, then a clarification message.

## 4. Follow-up patterns
| Utterance (after the given state) | `changes` |
|---|---|
| "Show revenue by region." (new) | full plan: `breakdown`, `dimensions: ["customers.region"]` |
| "Only the last six months." | `time: {range: {type: last_n, unit: month, n: 6}}` |
| "Compare it with the previous six months." | `comparison: {type: previous_period}` (intent may become `compare`) |
| "Which region contributed most to the decline?" | `intent: why`, `why: {dimensions: ["customers.region"]}` |
| "Now by category instead." | `dimensions: ["products.category"]` |
| "Just Electronics." | `filters_add: [{column: products.category, op: =, value: Electronics}]` |
| "Remove the filter." | `filters_remove: ["products.category"]` |
| "Show it monthly." | `intent: trend`, `time: {grain: month}` |
| "Top 5 only." | `intent: ranking`, `limit: 5` |
| "What about units?" | `metric: units` |
| "Why did it drop?" | `intent: why` (range and metric kept) |
| "Was it mainly a particular product category?" (after why) | `why: {dimensions: ["products.category"]}` |
| "Show the five products responsible for the largest decline." | `intent: ranking`, `dimensions: ["products.product_name"]`, `limit: 5`, `comparison` kept or set to `previous_period`, `sort: {by: delta, dir: asc}` |
| "Drill into the West region." (reference to `last_result_head`) | `filters_add: [{column: customers.region, op: =, value: West}]` |
| "What is the weather?" | `status: unsupported` |

Direction words: "decline", "drop", "fell" → `sort.dir: asc` on delta; "increase", "growth", "rose" → `desc`. The pipeline verifies the actual direction from data; the narrator words the result by real sign.

## 5. Reset and undo
- Starting over ("new question", "start over", or a clearly new subject) → `is_follow_up: false`, full plan.
- **Undo (P1):** "go back" restores the previous history plan.
- A dataset re-upload creates a new dataset and a new session.

## 6. Ambiguity handling
- Missing required information (e.g. "compare it" with no time range in state) → `status: needs_clarification` with one concise question; the session state does not change.
- A reference that cannot be resolved ("that one" with no `last_result_head`) → clarification.
- The UI shows the merged plan (and assumptions) after every turn so the user sees what "it" meant.

## 7. Tests
- Unit tests for every merge rule: replace, clear, deep merge of `time`, `filters_add`, `filters_remove`, intent change dropping invalid fields.
- The four-turn chain from `plan.md` section 6 produces: breakdown → time-limited → compared → why(region), with results equal to pandas.
- Restart test: after restarting the server, the next follow-up still patches the persisted plan.
- A trend plan followed by "Only the last six months." keeps its grain.
