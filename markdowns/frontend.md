# frontend.md: Web Interface

Stack: React + Vite + TypeScript, Tailwind CSS, ECharts via `echarts-for-react`, zustand. Dev server on 5173 proxies `/api` to 8000. The UI consumes the contract in `api-spec.md` exactly; types live in `frontend/src/types.ts`.

Design goals: (1) make the **glass box** obvious (plan, SQL, assumptions, data-quality warnings) because judges score correctness and technical depth; (2) make asking questions effortless; (3) look clean enough to be presentable without design polish.

## 1. Pages and flow
| Route | Page | Purpose |
|---|---|---|
| `/` | `UploadPage` | Drop files or "Use sample data"; after ingestion show understanding: tables, columns and roles, relationships, data-quality report |
| `/analyst` | `AnalystPage` | Chat with results (main demo screen) |
| `/dashboard` | `DashboardPage` | Generated management dashboard |

A persistent top bar shows the dataset name, tabs (Understand / Analyst / Dashboard), and a "New dataset" button. After a successful upload the app routes to `/analyst`; the "Understand" tab returns to the schema view.

## 2. Screens

### 2.1 Upload and understanding (`UploadPage`)
```
┌──────────────────────────────────────────────────────────────┐
│  [ Drag & drop Excel / CSV ]        [ Use sample data ]       │
├──────────────────────────────────────────────────────────────┤
│  Tables (5)               │  Relationships                    │
│  ▸ Sales    18,000 rows   │  sales.customer_id → customers... │
│  ▸ Customers  800         │  (confidence badges, graph)       │
│    columns: name, role,   │                                   │
│    type, null %           │  Data quality (6)                 │
│                           │  ● high  ● medium  ● low          │
│                           │  message + impact per issue       │
└──────────────────────────────────────────────────────────────┘
```
- Column rows show role chips (id, time, measure, dimension, text) and dtype; expanding a table shows sample values (from `/semantic`).
- Relationship graph: small node-link diagram (ECharts `graph` series) with edge labels for confidence.
- Data-quality list sorted by severity; each item shows count and impact text.
- Loading state for ingestion with staged messages ("Reading sheets", "Detecting types", "Finding relationships").

### 2.2 Analyst (`AnalystPage`)
```
┌─────────────────────────────────────────────────────────────┐
│ Chat thread (scroll)                                         │
│  You: Show revenue by region.                                │
│  ┌ Answer card ─────────────────────────────────────────┐    │
│  │ Narrative                                            │    │
│  │ ⚠ Data quality: 3% of customers have no region ...   │    │
│  │ [Chart]  [Table] toggle                              │    │
│  │ Period: Mar-Aug 2026   Assumptions: ...              │    │
│  │ ▸ How this was calculated (plan · SQL)               │    │
│  │ Suggestions: [Only last 6 months] [Why ...?]         │    │
│  └──────────────────────────────────────────────────────┘    │
├─────────────────────────────────────────────────────────────┤
│ [ Ask a question about your data...                 ] [Send] │
└─────────────────────────────────────────────────────────────┘
```
- The **answer card** shows, in order: narrative; data-quality banner (if any); chart (or KPI card) with a Chart/Table toggle; resolved period and assumptions as small chips; a collapsible "How this was calculated" panel with the plan (readable summary and raw JSON tab) and the SQL; suggestion chips (click sends the question).
- A "Current analysis" chip row above the input shows the active plan in plain words (metric, dimensions, filters, period, comparison) so follow-ups feel anchored. Each chip has an x to remove it (sends a patch-style question such as "Remove the filter").
- `why` results add a **drill path breadcrumb** (Category: Electronics → Region: West, with cumulative share) and a contribution chart.
- `needs_clarification`: shows the question with quick-reply buttons where possible. `unsupported` / `error`: a friendly message and, for errors, a "Retry" button.
- The input is disabled while a request is running; a skeleton card with staged text ("Understanding your question", "Running the analysis", "Writing the explanation") is shown.

### 2.3 Dashboard (`DashboardPage`)
```
┌──────────────────────────────────────────────────────────────┐
│ Summary (3-4 sentences)                       Period: Aug 2026│
├──────────────────────────────────────────────────────────────┤
│ [KPI][KPI][KPI][KPI][KPI][KPI]  (value, delta arrow, sparkline)│
├───────────────────────────────┬──────────────────────────────┤
│ Alerts (severity, click=Why)  │ Trend chart                  │
├───────────────────────────────┼──────────────────────────────┤
│ Breakdown 1                   │ Breakdown 2                  │
├───────────────────────────────┴──────────────────────────────┤
│ Top 10 ranking                       │ Detail table (alert)   │
└──────────────────────────────────────────────────────────────┘
```
- Each panel has an "Ask about this" button that opens `/analyst` with the panel's plan as `current_plan` (the dashboard call passes `session_id`).
- Alerts open the analysis attached to them (e.g. "Why did revenue fall?").
- Skeleton loading; dashboard generation can take up to about 15 s.

## 3. Components (`frontend/src/components/`)
| Component | Props (main) | Notes |
|---|---|---|
| `ChartRenderer` | `chart`, `result` | Picks ECharts / `KpiCard` / `ResultTable` by `chart.type`; applies formatters |
| `KpiCard` | `label, value, previous, deltaPct, format, sparkline?` | Green/red delta arrow; direction is by sign, colour meaning configurable per metric (default: up good) |
| `ResultTable` | `columns, rows, format?` | Sortable, sticky header, capped height, "showing N of M" when truncated |
| `PlanViewer` | `plan, sql, assumptions, resolvedTime, mode` | Readable summary + JSON + SQL with copy buttons |
| `DqBanner` | `warnings` | Collapsed by default when more than 2; severity colours |
| `RelationshipGraph` | `relationships, tables` | ECharts graph |
| `SuggestionChips` | `items, onPick` | |
| `AnswerCard` | `response` | Composes the above |
| `DrillPath` | `whyResult` | Breadcrumb with cumulative shares |
| `AlertList` | `alerts, onOpen` | |
| `CurrentAnalysis` | `plan, onRemove` | Plain-words summary chips |
| `UploadDropzone` | `onUploaded` | |

## 4. State (`store.ts`, zustand)
```
dataset: {id, name, tables, relationships, time, qualitySummary} | null
session: {id} | null
turns: Turn[]            // {question, response | null, status: pending|done|error}
currentPlan: Plan | null // from the last ok response
dashboard: DashboardResponse | null
ui: {expandedPlanId, chartOrTable per turn}
```
Actions: `uploadFiles`, `useSample`, `createSession`, `ask(question)`, `loadDashboard`, `openPanelInAnalyst(panel)`. Persist `dataset.id` and `session.id` in `sessionStorage` so a page refresh restores the conversation (`GET /sessions/{sid}/history`).

## 5. API client (`api.ts`)
Thin typed wrappers over `fetch` with a shared error handler that maps the `{status, code, message}` shape to a toast; 30 s client timeout for `/ask`, 60 s for `/dashboard` and uploads. No API keys or LLM calls in the browser.

## 6. Formatting
- Numbers use `Intl.NumberFormat("en-IN")` grouping by default (switchable to `en-US` in a settings menu). Currency symbol comes from a `currencySymbol` setting (default none); `value_format` from the response selects currency / count / percent / number formatting.
- Axis and tooltip formatters are applied on the frontend (`formatOption`) because functions cannot travel in JSON. Large axis values use compact notation with the locale's units.
- Dates: axis labels `MMM YYYY` for month grain, `DD MMM` for day grain.

## 7. Visual style
Tailwind with a neutral palette, one accent colour, cards with subtle borders, 8 px spacing grid, system font stack. Chart colours and rules are in `viz-rules.md`. Dark mode is out of scope.

## 8. Quality bar
- Every response state has a design: loading, ok, needs_clarification, unsupported, error, empty result ("No data in this period. Your data covers 2025-01-01 to 2026-08-31.").
- No console errors during the demo storyline; no unhandled promise rejections.
- Keyboard: Enter sends; Shift+Enter newline; focus returns to the input after each answer.
- Responsive down to laptop width (1280 px); mobile is out of scope.
- Accessibility basics: labels on inputs, colour is not the only carrier of severity (icons and text), chart has a table alternative.

## 9. Development plan
1. Build against `frontend/src/mocks/` (one response per intent) from Phase 3 onward.
2. Wire to the real API as each backend phase lands (`implementation.md` Phase 7 steps 7.1-7.4).
3. Final pass: run the demo storyline (`demo-script.md`) end to end and fix rough edges.
