# RootCause / AskData: REST API Reference

All endpoints are served by the FastAPI application on `http://localhost:8000`. Interactive OpenAPI documentation is accessible at `http://localhost:8000/docs`.

---

## 1. Datasets API

### 1.1 Upload Dataset
`POST /api/datasets`
Uploads one or more multi-sheet `.xlsx` or `.csv` files, ingests them into DuckDB, infers schemas and column roles, detects join relationships, profiles data quality, and builds the semantic layer.

- **Content-Type**: `multipart/form-data`
- **Body Parameters**:
  - `files`: File array (`.xlsx`, `.csv`)

#### Response (`200 OK`):
```json
{
  "status": "ok",
  "dataset_id": "ds_a8b9c1d2",
  "tables": [
    {
      "name": "sales",
      "display_name": "Sales",
      "role": "fact",
      "row_count": 16641,
      "columns": [
        {
          "name": "order_id",
          "display_name": "Order Id",
          "dtype": "VARCHAR",
          "role": "id",
          "null_pct": 0.0
        },
        {
          "name": "total_amount",
          "display_name": "Total Amount",
          "dtype": "DOUBLE",
          "role": "measure",
          "null_pct": 0.0
        }
      ]
    }
  ],
  "relationships": [
    {
      "from": "sales.customer_id",
      "to": "customers.customer_id",
      "type": "many_to_one",
      "confidence": 0.98
    }
  ],
  "time": {
    "primary_column": "sales.order_date",
    "min": "2025-01-01",
    "max": "2026-08-31",
    "anchor_date": "2026-08-31"
  },
  "quality_summary": {
    "high": 1,
    "medium": 3,
    "low": 1,
    "total": 5
  }
}
```

---

### 1.2 Load Retail Demo Dataset
`POST /api/datasets/sample`
Instantly initializes and indexes the built-in retail demo dataset (`sample_data/retail_demo.xlsx`).

#### Response (`200 OK`):
```json
{
  "status": "ok",
  "dataset_id": "ds_retail_sample",
  "tables": [ ... ],
  "relationships": [ ... ],
  "time": { ... },
  "quality_summary": { ... }
}
```

---

### 1.3 Get Semantic Layer
`GET /api/datasets/{id}/semantic`
Retrieves table definitions, column roles, registered metrics, and relationship graphs for a dataset.

#### Response (`200 OK`):
```json
{
  "dataset_id": "ds_retail_sample",
  "fact_table": "sales",
  "tables": { ... },
  "relationships": [ ... ],
  "metrics": [
    {
      "name": "revenue",
      "label": "Total Revenue",
      "table": "sales",
      "expr": "SUM(sales.total_amount)",
      "additive": true,
      "format": "currency",
      "time_behavior": "flow",
      "synonyms": ["sales", "turnover", "income"]
    }
  ],
  "time": {
    "anchor_date": "2026-08-31"
  }
}
```

---

### 1.4 Get Data Quality Issues
`GET /api/datasets/{id}/quality`
Retrieves all detected data quality issues with plain-English business impact statements.

#### Response (`200 OK`):
```json
{
  "dataset_id": "ds_retail_sample",
  "issues": [
    {
      "type": "negative_values",
      "severity": "high",
      "table": "sales",
      "column": "quantity",
      "row_count": 20,
      "pct": 0.0012,
      "description": "20 negative values found in quantity.",
      "impact": "May represent refunds or entry errors; aggregates may be understated."
    },
    {
      "type": "missing_values",
      "severity": "medium",
      "table": "customers",
      "column": "region",
      "row_count": 24,
      "pct": 0.03,
      "description": "24 missing values in customers.region.",
      "impact": "Unassigned rows will appear in breakdowns under the '(missing)' category."
    }
  ]
}
```

---

## 2. Conversational Sessions API

### 2.1 Create Analysis Session
`POST /api/sessions`
Initializes a stateful conversation thread associated with a dataset.

- **Request Body**:
```json
{
  "dataset_id": "ds_retail_sample"
}
```

- **Response (`200 OK`)**:
```json
{
  "session_id": "s_b7e41a9c",
  "dataset_id": "ds_retail_sample"
}
```

---

### 2.2 Ask Analytical Question
`POST /api/sessions/{session_id}/ask`
Processes a natural language question through the complete planner, DuckDB compiler, Why engine, number verifier, and visualization selector.

- **Request Body**:
```json
{
  "question": "Why did revenue fall last month?"
}
```

- **Response (`200 OK`)**:
```json
{
  "status": "ok",
  "message": null,
  "plan": {
    "intent": "why",
    "metric": "revenue",
    "time": {
      "range": { "unit": "month", "n": 1 }
    },
    "comparison": {
      "type": "previous_period"
    }
  },
  "assumptions": [
    "Defaulted 'why' target window to last month"
  ],
  "resolved_time": {
    "start": "2026-08-01",
    "end": "2026-08-31",
    "label": "August 2026",
    "baseline": {
      "start": "2026-07-01",
      "end": "2026-07-31",
      "label": "July 2026"
    }
  },
  "sql": "-- Executed Why Decomposition Engine in Python/DuckDB",
  "result": {
    "columns": ["Segment", "Delta", "Contribution", "Lift"],
    "rows": [
      ["Electronics", -58920.15, "83.2%", 2.1],
      ["Home & Kitchen", -11914.27, "16.8%", 0.9]
    ],
    "row_count": 2,
    "truncated": false
  },
  "chart": {
    "type": "contribution",
    "title": "Revenue Delta Decomposition by Category"
  },
  "narrative": "August 2026 revenue dropped by $70,834.42 (-14.2%) compared to July 2026. The decline was heavily concentrated in Electronics, which accounted for $58,920.15 (83.2%) of the total drop.",
  "dq_warnings": [],
  "why": {
    "direction": "decrease",
    "delta": -70834.42,
    "delta_pct": -14.16,
    "dimensions": [ ... ]
  },
  "suggestions": [
    "Was it mainly a particular product category?",
    "Show me the five products responsible for the largest decline",
    "Show inventory stock levels"
  ]
}
```

---

## 3. Executive Dashboard API

### 3.1 Generate Dashboard
`POST /api/datasets/{id}/dashboard`
Generates an executive briefing, 4–6 KPI sparklines, monthly trend line, category breakdown, entity ranking, and automated anomaly alerts in a single call.

#### Response (`200 OK`):
```json
{
  "status": "ok",
  "dataset_id": "ds_retail_sample",
  "generated_at": "2026-09-20T10:00:00Z",
  "executive_summary": "Overall revenue reached $3,892,410 across 16,641 orders. August 2026 revenue experienced a notable -14.2% dip compared to July, primarily driven by Electronics stockouts in the West region.",
  "kpis": [
    {
      "id": "revenue",
      "title": "Total Revenue",
      "value": 3892410.50,
      "formatted": "$3,892,411",
      "delta_pct": -14.2,
      "direction": "down",
      "period_label": "August 2026"
    }
  ],
  "charts": {
    "monthly_trend": { ... },
    "category_breakdown": { ... },
    "entity_ranking": { ... }
  },
  "alerts": [
    {
      "id": "alert_kpi_drop",
      "type": "kpi_drop",
      "severity": "high",
      "title": "Significant Monthly Revenue Decline",
      "description": "August 2026 revenue fell by 14.2% compared to July 2026.",
      "drill_question": "Why did revenue fall last month?"
    }
  ]
}
```

---

## 4. Settings & Health API

### 4.1 Health Check
`GET /api/health`
Verifies backend service health and active model configurations.

#### Response (`200 OK`):
```json
{
  "status": "ok",
  "llm_provider": "openrouter",
  "openrouter_model": "nex-agi/nex-n2.5-mini:free",
  "nvidia_nim_model": "meta/llama-3.2-11b-vision-instruct"
}
```

---

### 4.2 Get / Update Settings
`GET /api/settings` and `POST /api/settings`
Allows switching active providers and models at runtime.

- **Request Body (POST)**:
```json
{
  "active_provider": "nvidia_nim"
}
```
