# api-spec.md: HTTP API

Base path `/api`. JSON over HTTP; uploads use multipart. FastAPI generates OpenAPI at `/docs` automatically.

Where this file is more detailed than `architecture.md` section 10, this file wins. Refinements: `chart.value_format`, upload `notices`, optional `POST /datasets/sample`, error format.

## Conventions
- Domain outcomes of `/ask` and `/dashboard` return **HTTP 200** with a `status` field (`ok`, `needs_clarification`, `unsupported`, `error`).
- Transport-level problems use HTTP codes: 400 malformed request, 404 unknown dataset or session, 409 session busy, 413 file too large, 415 unsupported file type, 422 body validation, 500 unexpected.
- Error body (HTTP or `status: "error"`): `{"status": "error", "code": "query_timeout", "message": "The query took too long."}`. Codes: `unsupported_file_type`, `file_too_large`, `parse_failed`, `dataset_not_found`, `session_not_found`, `session_busy`, `llm_unavailable`, `plan_invalid`, `query_timeout`, `query_failed`, `internal_error`. Never return stack traces.
- Dates are ISO 8601 (`YYYY-MM-DD`). Numbers are JSON numbers; NaN/inf become null.
- CORS allows `http://localhost:5173`.

## Endpoints

### `GET /health`
`{"status": "ok"}`

### `POST /datasets`
Multipart with one or more `files` (.xlsx, .csv). Returns:
```json
{
  "dataset_id": "ds_ab12cd34",
  "tables": [
    {"name": "sales", "display_name": "Sales", "role": "fact", "row_count": 18000,
     "columns": [{"name": "order_date", "display_name": "Order Date", "dtype": "DATE",
                  "role": "time", "null_pct": 0.0}]}
  ],
  "relationships": [{"from": "sales.customer_id", "to": "customers.customer_id",
                     "type": "many_to_one", "confidence": 0.97}],
  "time": {"primary_column": "sales.order_date", "min": "2025-01-01",
           "max": "2026-08-31", "anchor_date": "2026-08-31"},
  "quality_summary": {"high": 1, "medium": 3, "low": 2, "total": 6},
  "notices": ["Sheet 'Notes' skipped: no data"]
}
```

### `POST /datasets/sample` (optional, P1)
Loads the bundled `sample_data/retail_demo.xlsx` and returns the same body as `POST /datasets`. Used by the "Use sample data" button for reliable demos.

### `GET /datasets/{id}/semantic`
The semantic layer JSON (`semantic-layer.md` section 2), including metrics and `quality_issues` counts; sample values are omitted for suppressed columns.

### `PATCH /datasets/{id}/semantic` (P1)
```json
{"columns": {"sales.discount_pct": {"role": "measure", "description": "..."}},
 "relationships": [{"from": "sales.product_id", "to": "products.product_id", "confirmed": true}],
 "metrics": {"revenue": {"label": "Net revenue", "synonyms": ["sales"]}}}
```
Returns the updated semantic layer.

### `GET /datasets/{id}/quality`
```json
{"issues": [{"id": "dq_001", "severity": "medium", "type": "missing_values",
             "table": "customers", "column": "region", "count": 24, "pct": 3.0,
             "message": "...", "impact": "..."}],
 "summary": {"high": 1, "medium": 3, "low": 2, "total": 6}}
```

### `POST /sessions`
Body `{"dataset_id": "ds_ab12cd34"}` → `{"session_id": "s_9f3a"}`.

### `POST /sessions/{sid}/ask`
Body `{"question": "Why did revenue fall last month?"}`. Response (`AskResponse`):
```json
{
  "status": "ok",
  "message": null,
  "plan": {},
  "assumptions": ["Compared with the previous month"],
  "resolved_time": {"start": "2026-08-01", "end": "2026-08-31", "label": "Aug 2026",
                    "baseline": {"start": "2026-07-01", "end": "2026-07-31", "label": "Jul 2026"}},
  "sql": "SELECT ...",
  "result": {"columns": ["region", "revenue"], "rows": [["West", 1250000]],
             "row_count": 4, "truncated": false},
  "chart": {"type": "bar_h", "value_format": "currency", "echarts_option": {}},
  "narrative": "Revenue fell 15.5% ...",
  "dq_warnings": [{"severity": "medium", "message": "3.0% of customers have no region ...",
                   "affected": ["customers.region"]}],
  "why": null,
  "suggestions": ["Show the trend for Electronics", "Which products drove the decline?"],
  "mode": "plan"
}
```
- `chart.type`: `kpi`, `line`, `bar`, `bar_h`, `grouped_bar`, `contribution`, `table`. `value_format`: `currency`, `count`, `percent`, `number`. For `kpi` the chart carries `{"kpi": {"value": ..., "previous": ..., "delta": ..., "delta_pct": ...}}` instead of an ECharts option.
- `why` holds the `WhyResult` (`analysis-modules.md` section 1) when `plan.intent` is `why`; otherwise null.
- `mode`: `plan` (structured plan) or `fallback_sql` (P1; `plan` is null).
- `needs_clarification` / `unsupported`: `message` is set, other fields are null or empty, session state is unchanged.
- HTTP 409 if the session is processing another question.

### `GET /sessions/{sid}/history`
`{"turns": [{"turn": 1, "question": "...", "plan": {}, "summary": "...", "timestamp": "..."}]}`

### `POST /datasets/{id}/dashboard`
Body `{"session_id": "s_9f3a"}` (optional; when given, the first panel's plan becomes the session's `current_plan`).
```json
{
  "status": "ok",
  "summary": "Revenue for Aug 2026 ...",
  "period": {"label": "Aug 2026", "baseline_label": "Jul 2026"},
  "kpis": [{"metric": "revenue", "label": "Revenue", "value": 4100000, "previous": 4850000,
            "delta": -750000, "delta_pct": -15.5, "value_format": "currency",
            "sparkline": [3.9, 4.1]}],
  "panels": [{"id": "p1", "title": "Monthly revenue", "plan": {}, "sql": "...",
              "result": {}, "chart": {}, "insight": "..."}],
  "alerts": [{"id": "a1", "severity": "high", "type": "kpi_drop", "title": "...",
              "detail": "...", "plan": {}}],
  "dq_warnings": []
}
```

## Limits and behaviour
- Max upload size per file: `config.py` (default 100 MB); number of files per upload: 20.
- Result rows returned: at most `MAX_RESULT_ROWS`.
- `/ask` target latency: about 8 s or less; the LLM client times out at 30 s and returns `llm_unavailable`.
- Ingestion is synchronous (the response returns after tables are typed, profiled and the semantic layer is built). Long uploads show a spinner in the frontend.

## Example (curl)
```
curl -F "files=@sample_data/retail_demo.xlsx" http://localhost:8000/api/datasets
curl -X POST http://localhost:8000/api/sessions -H "Content-Type: application/json" -d '{"dataset_id":"ds_ab12cd34"}'
curl -X POST http://localhost:8000/api/sessions/s_9f3a/ask -H "Content-Type: application/json" -d '{"question":"Show me monthly revenue for 2026"}'
```

## Mocking for the frontend
`frontend/src/mocks/` holds one example response per intent (kpi, trend, breakdown, ranking, compare, why, dashboard, needs_clarification, error). The frontend can be built against them before the backend is ready. `types.ts` mirrors the shapes above.
