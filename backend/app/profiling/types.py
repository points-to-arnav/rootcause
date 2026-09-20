import re
from datetime import datetime, date
from typing import Any, List, Optional, Tuple
import duckdb
import pandas as pd

DATE_FORMATS = [
    "%Y-%m-%d", "%Y/%m/%d",
    "%d/%m/%Y", "%m/%d/%Y",
    "%d-%m-%Y", "%m-%d-%Y",
    "%d-%b-%Y", "%b %d, %Y",
    "%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S",
    "%d/%m/%Y %H:%M:%S", "%m/%d/%Y %H:%M:%S"
]

def try_parse_date(val: Any) -> Optional[datetime]:
    if pd.isna(val) or val is None or str(val).strip() == "":
        return None
    if isinstance(val, (datetime, pd.Timestamp)):
        return val
    if isinstance(val, date):
        return datetime(val.year, val.month, val.day)
    s = str(val).strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt)
        except Exception:
            continue
    return None

def infer_column_type(values: List[Any], col_name: str) -> Tuple[str, List[str]]:
    """
    Infers the column data type from non-null values.
    Returns (dtype, notices/issues).
    dtype in ['BOOLEAN', 'BIGINT', 'DOUBLE', 'DATE', 'TIMESTAMP', 'VARCHAR'].
    """
    notices = []
    non_nulls = [v for v in values if pd.notna(v) and v is not None and str(v).strip() != ""]
    total = len(non_nulls)
    if total == 0:
        return "VARCHAR", notices

    # 1. Check BOOLEAN
    bool_words = {"true", "false", "yes", "no", "y", "n", "t", "f"}
    bool_matches = sum(1 for v in non_nulls if str(v).strip().lower() in bool_words)
    if bool_matches / total >= 0.95:
        return "BOOLEAN", notices

    # 2. Check DATE / TIMESTAMP
    date_matches = 0
    has_time_component = False
    formats_used = set()
    day_first_clues = 0
    month_first_clues = 0

    for v in non_nulls:
        # Check string date clues for DD/MM vs MM/DD
        s = str(v).strip()
        m = re.match(r"^(\d{1,2})[/.-](\d{1,2})[/.-](\d{2,4})", s)
        if m:
            p1, p2 = int(m.group(1)), int(m.group(2))
            if p1 > 12 >= p2:
                day_first_clues += 1
            elif p2 > 12 >= p1:
                month_first_clues += 1

        dt = try_parse_date(v)
        if dt is not None:
            date_matches += 1
            if dt.hour != 0 or dt.minute != 0 or dt.second != 0:
                has_time_component = True

    if date_matches / total >= 0.90:
        if day_first_clues > 0 and month_first_clues == 0:
            notices.append(f"Column '{col_name}' dates resolved as day-first (DD/MM/YYYY).")
        elif month_first_clues > 0 and day_first_clues == 0:
            notices.append(f"Column '{col_name}' dates resolved as month-first (MM/DD/YYYY).")
        elif day_first_clues > 0 and month_first_clues > 0:
            notices.append(f"Column '{col_name}' has mixed date conventions; parsed with flexible matching.")

        return "TIMESTAMP" if has_time_component else "DATE", notices

    # 3. Check BIGINT
    # Codes with leading zero and length > 1 stay VARCHAR
    has_leading_zero = any(isinstance(v, str) and v.startswith("0") and len(v) > 1 and v.isdigit() for v in non_nulls)
    if not has_leading_zero:
        int_matches = 0
        for v in non_nulls:
            s = str(v).replace(",", "").strip()
            if re.match(r"^[+-]?\d+$", s):
                int_matches += 1
        if int_matches / total >= 0.95:
            return "BIGINT", notices

    # 4. Check DOUBLE
    double_matches = 0
    for v in non_nulls:
        s = str(v).replace(",", "").replace("$", "").replace("₹", "").replace("€", "").replace("£", "").replace("%", "").strip()
        try:
            float(s)
            double_matches += 1
        except Exception:
            continue
    if double_matches / total >= 0.95:
        return "DOUBLE", notices

    # 5. Fallback VARCHAR
    return "VARCHAR", notices

def cast_and_recreate_table(con: duckdb.DuckDBPyConnection, table_name: str, col_types: dict[str, str]) -> List[str]:
    """
    Alters table columns to their strongly typed versions in DuckDB.
    Returns any casting notices.
    """
    notices = []
    cast_exprs = []

    for col, dtype in col_types.items():
        if dtype == "DATE":
            cast_exprs.append(f"TRY_CAST(\"{col}\" AS DATE) AS \"{col}\"")
        elif dtype == "TIMESTAMP":
            cast_exprs.append(f"TRY_CAST(\"{col}\" AS TIMESTAMP) AS \"{col}\"")
        elif dtype == "BIGINT":
            cast_exprs.append(f"TRY_CAST(REPLACE(CAST(\"{col}\" AS VARCHAR), ',', '') AS BIGINT) AS \"{col}\"")
        elif dtype == "DOUBLE":
            cast_exprs.append(f"TRY_CAST(REGEXP_REPLACE(CAST(\"{col}\" AS VARCHAR), '[^0-9.-]', '', 'g') AS DOUBLE) AS \"{col}\"")
        elif dtype == "BOOLEAN":
            cast_exprs.append(f"TRY_CAST(\"{col}\" AS BOOLEAN) AS \"{col}\"")
        else:
            cast_exprs.append(f"CAST(\"{col}\" AS VARCHAR) AS \"{col}\"")

    select_clause = ", ".join(cast_exprs)
    con.execute(f'CREATE OR REPLACE TABLE "{table_name}" AS SELECT {select_clause} FROM "{table_name}"')
    return notices
