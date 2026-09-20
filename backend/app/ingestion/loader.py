import os
import re
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import duckdb
import pandas as pd
from app.config import settings

def sanitize_name(name: str, existing: set[str], prefix: str = "col") -> str:
    """
    Sanitizes table and column names to unique snake_case:
    1. Unicode NFKD normalise, fold to ASCII
    2. Lowercase
    3. Replace non-alphanumeric with '_'
    4. Collapse repeated '_' and strip
    5. Disallow empty or leading digits
    6. De-duplicate with suffix _2, _3
    """
    s = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode("ascii")
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")

    if not s:
        s = prefix
    elif s[0].isdigit():
        s = f"{prefix[0]}_{s}"

    candidate = s
    idx = 2
    while candidate in existing:
        candidate = f"{s}_{idx}"
        idx += 1

    existing.add(candidate)
    return candidate

def detect_header_and_clean(df_raw: pd.DataFrame) -> Tuple[pd.DataFrame, List[str], List[str]]:
    """
    Detects the header row within the top 10 rows:
    The header is the first row where at least 60% of cells are non-empty text,
    and the following row has differing or data cells.
    Returns (df_data, display_columns, notices).
    """
    notices = []
    header_idx = 0
    max_check = min(10, len(df_raw))

    for r in range(max_check):
        row = df_raw.iloc[r]
        non_empty = [x for x in row if pd.notna(x) and str(x).strip() != ""]
        if not non_empty:
            continue
        text_count = sum(1 for x in non_empty if isinstance(x, str) and not x.replace(".", "", 1).isdigit())
        if len(non_empty) > 0 and (text_count / len(df_raw.columns)) >= 0.50:
            header_idx = r
            break

    if header_idx > 0:
        notices.append(f"Header found at row {header_idx + 1}; {header_idx} leading rows dropped.")

    # Slice header and data
    raw_headers = list(df_raw.iloc[header_idx])
    df_data = df_raw.iloc[header_idx + 1:].copy()

    # Drop completely empty rows and columns
    df_data.dropna(how="all", inplace=True)
    df_data.dropna(axis=1, how="all", inplace=True)

    # Process header names
    display_columns = []
    for c_idx, h in enumerate(raw_headers):
        if c_idx >= len(df_data.columns):
            break
        if pd.isna(h) or str(h).strip() == "":
            col_name = f"Column_{c_idx + 1}"
            notices.append(f"Blank header cell at column {c_idx + 1} named '{col_name}'.")
        else:
            col_name = str(h).strip()
        display_columns.append(col_name)

    df_data.columns = display_columns
    df_data.reset_index(drop=True, inplace=True)
    return df_data, display_columns, notices

def load_file_to_dfs(file_path: str) -> Tuple[Dict[str, Tuple[pd.DataFrame, str]], List[str]]:
    """
    Loads an Excel or CSV file into a dictionary:
    { table_key: (dataframe, sheet_or_filename_display_name) }
    """
    notices = []
    tables = {}
    path = Path(file_path)
    suffix = path.suffix.lower()

    if suffix in [".xlsx", ".xls"]:
        excel = pd.ExcelFile(file_path)
        for sheet in excel.sheet_names:
            df_sheet = pd.read_excel(excel, sheet_name=sheet, header=None, dtype=object)
            if df_sheet.empty or len(df_sheet) < 2:
                notices.append(f"Sheet '{sheet}' skipped: fewer than 2 rows.")
                continue
            df_clean, _, sub_notices = detect_header_and_clean(df_sheet)
            notices.extend(sub_notices)
            tables[sheet] = (df_clean, sheet)

    elif suffix in [".csv", ".tsv"]:
        # Try multiple encodings
        encodings = ["utf-8", "utf-8-sig", "latin-1"]
        df_csv = None
        for enc in encodings:
            try:
                df_csv = pd.read_csv(file_path, encoding=enc, header=None, dtype=object, sep=None, engine="python")
                break
            except Exception:
                continue

        if df_csv is None:
            raise ValueError(f"Unable to parse CSV {file_path} with supported encodings (utf-8, latin-1).")

        df_clean, _, sub_notices = detect_header_and_clean(df_csv)
        notices.extend(sub_notices)
        table_name = path.stem
        tables[table_name] = (df_clean, table_name)
    else:
        raise ValueError(f"Unsupported file format: {suffix}. Expected .xlsx or .csv.")

    return tables, notices

def ingest_to_duckdb(dataset_id: str, file_paths: List[str]) -> Tuple[str, Dict[str, Any], List[str]]:
    """
    Ingests all tables from file_paths into DATA_DIR/{dataset_id}/data.duckdb.
    Returns:
    - duckdb_path: Path to the created DuckDB file
    - schema_meta: Metadata mapping table_name -> columns info
    - notices: Any warnings/notices encountered during load
    """
    dataset_dir = os.path.join(settings.DATA_DIR, dataset_id)
    os.makedirs(dataset_dir, exist_ok=True)
    db_path = os.path.join(dataset_dir, "data.duckdb")

    # Remove existing db if recreating
    if os.path.exists(db_path):
        os.remove(db_path)

    all_tables = {}
    all_notices = []

    for fp in file_paths:
        dfs, notices = load_file_to_dfs(fp)
        all_notices.extend(notices)
        for k, v in dfs.items():
            all_tables[k] = v

    if not all_tables:
        raise ValueError("No valid data tables found in uploaded files.")

    # Open DuckDB writer connection
    con = duckdb.connect(db_path, read_only=False)
    existing_tables = set()
    schema_meta = {}

    try:
        for orig_name, (df, display_table_name) in all_tables.items():
            sanitized_tbl = sanitize_name(orig_name, existing_tables, prefix="tbl")
            existing_cols = set()
            col_mapping = {}

            # Sanitize column names
            for col in df.columns:
                sanitized_c = sanitize_name(col, existing_cols, prefix="col")
                col_mapping[col] = sanitized_c

            df_renamed = df.rename(columns=col_mapping).copy()

            # Register and create table in DuckDB
            con.register("temp_df", df_renamed)
            con.execute(f'CREATE TABLE "{sanitized_tbl}" AS SELECT * FROM temp_df')
            con.unregister("temp_df")

            schema_meta[sanitized_tbl] = {
                "display_name": display_table_name,
                "original_name": orig_name,
                "row_count": len(df_renamed),
                "columns": {
                    sanitized_c: {"display_name": orig_c}
                    for orig_c, sanitized_c in col_mapping.items()
                }
            }
    finally:
        # Strictly close writer connection!
        con.close()

    return db_path, schema_meta, all_notices
