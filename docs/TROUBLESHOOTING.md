# RootCause / AskData: Troubleshooting & FAQ Guide

This guide addresses common issues, edge cases, and optimization strategies when deploying or developing with RootCause.

---

## 1. LLM Provider Issues & Rate Limits (HTTP 429)

### Issue: "OpenRouter returned 429: Too Many Requests"
- **Cause**: Free tier public endpoints on OpenRouter (such as `qwen` or `gemma` free models) experience high global demand and occasional upstream throttling.
- **RootCause Automatic Handling**: RootCause automatically intercepts HTTP 429 errors and retries the request using the secondary fallback provider (**NVIDIA NIM**).
- **Resolution Options**:
  1. **Change the OpenRouter Model**: In the UI Settings modal or in `backend/.env`, use a faster free model such as `nex-agi/nex-n2.5-mini:free` or `meta-llama/llama-3.2-3b-instruct:free`.
  2. **Switch Active Provider to NVIDIA NIM**:
     - In the UI top navigation bar, click the Model badge and select **NVIDIA NIM**.
     - Or set `LLM_PROVIDER=nvidia_nim` in `backend/.env`.
  3. **Use a Paid Key on OpenRouter**: If you add credits to your OpenRouter account, rate limits on standard models are removed.

---

## 2. DuckDB Concurrency & Database Locks

### Issue: `duckdb.IOException: Could not set lock on file ...`
- **Cause**: DuckDB allows multiple concurrent read connections, but only one write connection at a time.
- **RootCause Design**:
  - Ingestion (`app.ingestion.loader` and `routes_datasets.py`) opens a write connection, writes all tables, creates indexes, and **immediately closes the connection**.
  - All query execution (`app.planner.executor`) uses explicit `read_only=True` connections:
    ```python
    duckdb.connect(db_path, read_only=True)
    ```
- **If a lock error occurs**:
  - Check if another background Python process is holding a write lock on `data.duckdb`.
  - Kill orphaned processes:
    ```bash
    fuser -k backend/data/*/data.duckdb
    ```

---

## 3. Date Parsing & Calendar Ambiguities

### Issue: "Inconsistent dates detected" or "DD/MM vs MM/DD confusion"
- **Cause**: Excel workbooks often mix string formatted dates (`"15/08/2026"`) with serial date numbers or ISO strings (`"2026-08-15"`).
- **RootCause Heuristic**:
  - `app.profiling.types.infer_column_type` examines date samples. If days greater than 12 appear before the slash (`>12/MM`), it automatically selects `DD/MM/YYYY` format.
  - All dates are cast into standard DuckDB `DATE` or `TIMESTAMP` columns during ingestion.
  - Inconsistent rows are flagged under Data Quality warnings so you are aware of formatting variance.

---

## 4. Number Verification Mismatch

### Issue: Narrative displays templated text instead of LLM prose
- **Cause**: RootCause enforces a strict zero-hallucination verification gate (`app.narrator.verify`). Every number mentioned in the LLM's narrative is matched against actual DuckDB result cells.
- **Behavior**: If the LLM generates a number not present in the pre-computed aggregates (e.g. hallucinating a growth figure of $+25.5\%$ when the data shows $+18.2\%$), the text is automatically rejected and replaced by a deterministic, mathematically exact templated sentence:
  ```
  "Total revenue was $3,892,411 across 16,641 orders."
  ```
- **Confidence Badge**: When the narrative matches DuckDB data with 100% precision, the UI displays the green **"✓ DuckDB Verified"** badge.

---

## 5. Frontend & Node Build Troubleshooting

### Issue: `npm run build` fails with `TS1484` or `TS6133`
- **Cause**: TypeScript `verbatimModuleSyntax` requires type-only imports (`import type { ... }`).
- **Resolution**:
  - In `frontend/tsconfig.app.json`, `"verbatimModuleSyntax": false` and `"noUnusedLocals": false` are pre-configured to ensure clean, uninterrupted Vite bundling.
  - Ensure all dependencies are installed: `npm install` in `frontend/`.

---

## 6. Large Datasets & Memory Optimization

- By default, query execution is bounded by:
  - `MAX_RESULT_ROWS = 1000`: Queries returning thousands of rows are capped to prevent browser DOM freezes.
  - `QUERY_TIMEOUT_S = 20`: A watchdog interrupt aborts any long-running accidental Cartesian product joins.
  - `WHY_MAX_CARDINALITY = 50`: Dimensions with $>50$ distinct values are filtered or grouped into top segments + `(other)` to keep root-cause analyses instant.
