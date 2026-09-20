# data-engine.md: Ingestion, Profiling, Data Quality, Execution

Scope: everything between "file uploaded" and "typed, profiled DuckDB tables with a list of data-quality issues". The semantic layer (`semantic-layer.md`) and the planner/compiler (`query-plan-spec.md`) build on this.

Where this file is more detailed than `architecture.md`, this file wins.

## 1. Pipeline
```
upload (files[]) → save to DATA_DIR/{dataset_id}/raw/
   → loader: read each sheet/CSV as raw cells
   → header detection + cleaning + name sanitising
   → type inference (per column) → typed DataFrame
   → write DuckDB tables (writer connection, then close)
   → profiler (read-only connection) → column stats
   → DQ checks → issues[]
   → semantic layer build (roles, relationships, metrics, value index)
```

## 2. Dataset directory
```
DATA_DIR/{dataset_id}/
├── raw/                 original uploaded files (never modified)
├── data.duckdb          typed tables
├── profile.json         per-table, per-column stats
├── quality.json         issues[]
├── semantic.json        semantic layer
└── sessions/{sid}.json  conversation state
```
`dataset_id` = `ds_` + first 8 hex chars of a uuid4.

## 3. Loader (`ingestion/loader.py`)
**Formats:** `.xlsx` and `.csv` (P0); `.xls` (needs `xlrd`) and `.tsv` (P1). Anything else is rejected with `unsupported_file_type`. A size limit is set in `config.py` (default 100 MB per file).

**Excel:** `pd.read_excel(path, sheet_name=None, header=None, dtype=object)`, so native cell types (datetime, float, str) survive. Every sheet becomes one table. Sheets with fewer than 2 non-empty rows or no non-empty columns are skipped and listed in `notices`.

**CSV:** try encodings `utf-8`, `utf-8-sig`, then `latin-1`; sniff the delimiter among `,` `;` `\t` `|`; read everything as text (`dtype=str`, `keep_default_na=False`, then treat empty strings as null) so type inference decides types.

**Header detection:** within the first 10 rows, the header is the first row where at least 60% of cells are non-empty text and the following row has at least one non-text or differing-type cell (or the row is followed by data). Rows above it are dropped and noted. If nothing qualifies, row 0 is the header. Blank header cells become `column_<position>` (1-based) and raise a notice.

**Cleaning:** drop rows and columns that are entirely empty; strip leading/trailing whitespace from text cells and headers; keep original header text as `display_name`.

**Name sanitising** (tables and columns):
1. Unicode NFKD normalise, fold to ASCII.
2. Lowercase.
3. Replace every character outside `[a-z0-9]` with `_`.
4. Collapse repeated `_`; strip `_` at both ends.
5. Empty result → `col` (columns) or `table` (tables). Leading digit → prefix `c_` (columns) or `t_` (tables).
6. De-duplicate within scope with `_2`, `_3`, ...

Examples: `Order Date` → `order_date`, `Sub-Category` → `sub_category`, `Sales ($)` → `sales`. A CSV file `orders.csv` → table `orders`; sheet `Sales` → `sales`.

**Limitations (documented, not solved):** merged cells (only the top-left cell holds a value), multi-row headers, footer/total rows (flagged by `summary_row` in P1), sheets that are separate years of the same schema (they remain separate tables, no union).

## 4. Type inference (`profiling/types.py`)
Applied per column on non-null values, in this order; the first type that accepts at least 95% of non-null values wins.

| Order | Type | Accepts |
|---|---|---|
| 1 | BOOLEAN | column contains only values from {true,false,yes,no,y,n,t,f} (case-insensitive), or only {0,1} with the name matching `is_|has_|flag|active` |
| 2 | BIGINT | integer-looking values; thousands separators (`1,234` and Indian `1,23,456`) and a leading `+`/`-` allowed |
| 3 | DOUBLE | decimals; currency symbols (`₹ $ € £`), thousands separators, trailing `%` (value kept as written, not divided by 100; the column is noted as percent) |
| 4 | DATE / TIMESTAMP | see below |
| 5 | VARCHAR | everything else |

**Exceptions:**
- Codes with a leading zero and length > 1 (e.g. `00123`) stay VARCHAR.
- Native Excel/pandas datetimes are accepted directly. A datetime column is DATE if every value is at midnight, otherwise TIMESTAMP.
- Values that fail to parse in an otherwise-typed column become NULL and are counted in an `invalid_values` issue.
- Money and measures are stored as DOUBLE. Tests compare with a relative tolerance of 1e-6.

**Date parsing.** Formats tried: `YYYY-MM-DD`, `YYYY/MM/DD`, `DD/MM/YYYY`, `MM/DD/YYYY`, `DD-MM-YYYY`, `DD-Mon-YYYY`, `Mon DD, YYYY`, and the same with time parts. Rules:
1. A column is a date column when at least 95% of non-null values parse under the allowed formats (or are native datetimes).
2. `DD/MM` vs `MM/DD` ambiguity is resolved from unambiguous rows: if any value has a first part > 12, the format is day-first; if any has a second part > 12, month-first. If both occur, the column is flagged inconsistent and each value is parsed by whichever format is valid. If none is decisive, default to day-first and raise an `inconsistent_dates` issue noting the assumption.
3. If more than one format was needed to parse the column, raise `inconsistent_dates` with the formats found and their counts.
4. Excel serial numbers stored as numbers are not converted in P0 (P1).

## 5. Writing to DuckDB
- Open a writer connection to `data.duckdb`, register the typed DataFrame, `CREATE TABLE "<name>" AS SELECT * FROM <df>`, close.
- The writer connection is always closed before any read-only connection is opened. Never open the same file with mixed read/write configuration in one process.
- All later access uses `duckdb.connect(path, read_only=True)`.

## 6. Profiler (`profiling/profiler.py`)
Per table: `row_count`, `column_count`. Per column (computed in DuckDB SQL over a read-only connection):

| Stat | How |
|---|---|
| `null_count`, `null_pct` | `COUNT(*) - COUNT(col)` |
| `distinct`, `distinct_ratio` | `COUNT(DISTINCT col)` over non-null rows |
| `min`, `max` | numeric and date columns |
| `mean`, `std`, `q1`, `q3` | numeric columns (`AVG`, `STDDEV_SAMP`, `quantile_cont`) |
| `top_values` | 5 most frequent values with counts |
| `samples` | up to 5 distinct values (most frequent first); text truncated to 40 characters |

**Sample suppression:** no samples are stored for columns whose name matches `email|phone|mobile|address|ssn|aadhaar|pan|password|passport|iban|card`. The `samples` list is empty for them, so they never reach the LLM.

Output: `profile.json`.

## 7. Data-quality checks (`profiling/quality.py`)
Issue record:
```json
{"id": "dq_001", "severity": "medium", "type": "missing_values",
 "table": "customers", "column": "region", "count": 24, "pct": 3.0,
 "message": "3.0% of customers have no region.",
 "impact": "Revenue by region groups these customers under '(missing)'."}
```
`pct` is a percentage (0-100) of the table's rows unless stated otherwise. `column` is null for table-level issues.

| Type | Detection | Severity | Impact text (template) |
|---|---|---|---|
| `missing_values` | `null_pct > 0` | high ≥ 20%, medium ≥ 2%, low > 0 | "Rows with no {column} appear under '(missing)' in {column} breakdowns and are excluded from filters on it." |
| `duplicate_rows` | fully identical rows in a table | high ≥ 1% of rows, else medium | "Duplicated rows are counted twice in sums and counts (about {pct}% of rows)." |
| `duplicate_id` | id-role column expected to be unique (name equals `<table>_id`, `id`, or `<singular table>_id`) has repeated values **beyond exact duplicate rows** | high ≥ 1%, else medium | "Repeated {column} values may double count or duplicate joined rows." |
| `negative_values` | measure column normally non-negative (name matches `quantity|qty|price|amount|cost|revenue|sales|units|stock|discount`) with any negative | medium | "Negative values reduce totals; they may be returns or data-entry errors." |
| `outliers` | measure column, n ≥ 30, IQR > 0, values outside Q1 − 3·IQR / Q3 + 3·IQR | medium if outliers hold more than 5% of the column sum, else low | "Extreme values can skew totals and averages (largest: {max})." |
| `inconsistent_dates` | more than one date format needed, or ambiguity assumed (section 4) | medium | "Dates in mixed formats were normalised; {n} values needed a different format. If wrong, monthly figures may shift." |
| `invalid_values` | values turned to NULL by type inference | high ≥ 20%, medium ≥ 2%, low > 0 | "{n} values could not be read as {type} and were ignored." |
| `orphan_keys` | (added by the semantic layer step) child key values with no parent | medium ≥ 1% of child rows, else low | "Rows whose {column} has no match in {parent} appear under '(missing)' in breakdowns by {parent} columns." |
| `constant_column` | one distinct value, more than one row | low | "{column} never varies, so it cannot explain differences." |
| `summary_row` (P1) | row whose first text cell matches `total|grand total|subtotal` | medium | "Total rows would double count if summed." |

**Run order:** `invalid_values` and `inconsistent_dates` come from type inference; then `duplicate_rows`, `duplicate_id`, `missing_values`, `negative_values`, `outliers`, `constant_column`. `orphan_keys` is added after relationship detection.

**Policy:** issues are reported, never auto-fixed. Duplicates, negatives and outliers stay in the data (P1 adds an exclude-duplicates toggle).

**Attaching to answers:** an issue becomes a `dq_warning` on an answer when its `table.column` is used by the plan (metric columns, dimensions, filters, time column) or, for table-level issues, when the plan's fact table matches. Warnings carry the quantified impact.

## 8. Query execution (`planner/executor.py`)
- Read-only connection per request (`connection.cursor()` for concurrency inside a process).
- Row cap: `MAX_RESULT_ROWS`; result reports `truncated: true` when the cap is hit.
- Timeout: a watchdog thread calls `connection.interrupt()` after `QUERY_TIMEOUT_S`; the API returns `status: "error"` with code `query_timeout`.
- Values are bound as parameters (`?`).
- Result rows are converted to JSON-safe types: dates as ISO strings, NaN/inf as null, Decimal as float.

## 9. Test requirements
- Fixtures: `sample_data/retail_demo.xlsx` and small hand-made CSV/Excel edge files (bad headers, mixed date formats, leading-zero codes, semicolon-delimited CSV, latin-1 CSV, empty sheet).
- Every inference and DQ rule has a positive and a negative test.
- Profile numbers are checked against independent pandas calculations.
- Idempotence: loading the same file twice gives identical typed tables.
