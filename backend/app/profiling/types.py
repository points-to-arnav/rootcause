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

# strptime patterns DuckDB tries, in this order, on text dates. TRY_CAST is tried
# first and only understands ISO, so anything written DD/MM/YYYY needs these.
_NEUTRAL_FORMATS = ["%Y/%m/%d", "%d-%b-%Y", "%b %d, %Y"]
_DAY_FIRST_FORMATS = ["%d/%m/%Y", "%d-%m-%Y"]
_MONTH_FIRST_FORMATS = ["%m/%d/%Y", "%m-%d-%Y"]

_LEADING_PARTS = r"'^(\d{1,2})[/.-](\d{1,2})[/.-](\d{2,4})'"


def _text_date_expression(col: str, target: str, month_first: bool) -> str:
    """
    SQL that reads a column of mixed native and text dates as `target`.

    Every format is always attempted; `month_first` only decides which convention
    wins for a value that is valid both ways (01/02/2025). A value that is only
    valid one way (16/01/2025) is read correctly whichever comes first.
    """
    text = f'CAST("{col}" AS VARCHAR)'
    ordered = _NEUTRAL_FORMATS + (
        _MONTH_FIRST_FORMATS + _DAY_FIRST_FORMATS if month_first
        else _DAY_FIRST_FORMATS + _MONTH_FIRST_FORMATS
    )
    ordered += [f"{fmt} %H:%M:%S" for fmt in ordered]

    attempts = [f'TRY_CAST("{col}" AS {target})']
    attempts += [f"TRY_CAST(TRY_STRPTIME({text}, '{fmt}') AS {target})" for fmt in ordered]
    return "COALESCE(" + ", ".join(attempts) + ")"


def _convert_text_dates(
    con: duckdb.DuckDBPyConnection, table_name: str, col: str, target: str
) -> Tuple[str, List[dict]]:
    """
    Returns (select expression, quality issues) for a date column stored as text.

    Follows the data-engine spec: DD/MM vs MM/DD is settled by unambiguous values
    (a first part above 12 means day-first, a second part above 12 means
    month-first); with no such value, day-first is assumed and the issue says so.
    Values that match no format become NULL and are counted, never dropped quietly.
    """
    text = f'CAST("{col}" AS VARCHAR)'
    clues = con.execute(
        f"""
        SELECT
          COUNT(*) FILTER (WHERE regexp_matches(s, {_LEADING_PARTS})
              AND TRY_CAST(regexp_extract(s, {_LEADING_PARTS}, 1) AS INTEGER) > 12
              AND TRY_CAST(regexp_extract(s, {_LEADING_PARTS}, 2) AS INTEGER) <= 12),
          COUNT(*) FILTER (WHERE regexp_matches(s, {_LEADING_PARTS})
              AND TRY_CAST(regexp_extract(s, {_LEADING_PARTS}, 2) AS INTEGER) > 12
              AND TRY_CAST(regexp_extract(s, {_LEADING_PARTS}, 1) AS INTEGER) <= 12)
        FROM (SELECT {text} AS s FROM "{table_name}") WHERE s IS NOT NULL
        """
    ).fetchone()
    day_first_clues, month_first_clues = int(clues[0]), int(clues[1])
    month_first = month_first_clues > 0 and day_first_clues == 0
    expression = _text_date_expression(col, target, month_first)

    total, needed_other_format, unreadable = con.execute(
        f"""
        SELECT
          COUNT(*),
          COUNT(*) FILTER (WHERE TRY_CAST("{col}" AS {target}) IS NULL AND {expression} IS NOT NULL),
          COUNT(*) FILTER (WHERE {expression} IS NULL)
        FROM (SELECT * FROM "{table_name}") WHERE "{col}" IS NOT NULL AND TRIM({text}) <> ''
        """
    ).fetchone()

    issues: List[dict] = []
    # A column written consistently in one non-ISO format (every value 16-01-2025)
    # is just a format, not a problem. It is worth reporting only when formats are
    # mixed, both conventions occur, or the day/month order had to be assumed.
    parsed = total - unreadable
    mixed_formats = 0 < needed_other_format < parsed
    ambiguous = not day_first_clues and not month_first_clues
    both_conventions = bool(day_first_clues and month_first_clues)
    if needed_other_format and (mixed_formats or ambiguous or both_conventions):
        if day_first_clues and month_first_clues:
            convention = "Both day-first and month-first values occur, so each was read the way it is valid."
        elif day_first_clues:
            convention = "The dates were read as day-first (DD/MM/YYYY)."
        elif month_first_clues:
            convention = "The dates were read as month-first (MM/DD/YYYY)."
        else:
            convention = "Nothing settled day-first versus month-first, so day-first was assumed."
        issues.append({
            "id": f"dq_dates_{table_name}_{col}",
            "severity": "medium",
            "type": "inconsistent_dates",
            "table": table_name,
            "column": col,
            "count": int(needed_other_format),
            "pct": round(needed_other_format / total * 100, 2),
            "message": (
                f"{needed_other_format} of {total} '{col}' values were stored as text in a "
                f"different date format and were converted."
            ),
            "impact": f"{convention} If that is wrong, monthly figures may shift.",
        })
    if unreadable:
        pct = round(unreadable / total * 100, 2)
        issues.append({
            "id": f"dq_dates_invalid_{table_name}_{col}",
            "severity": "high" if pct >= 20.0 else ("medium" if pct >= 2.0 else "low"),
            "type": "invalid_values",
            "table": table_name,
            "column": col,
            "count": int(unreadable),
            "pct": pct,
            "message": f"{unreadable} '{col}' values could not be read as dates ({pct}%).",
            "impact": "Those rows are treated as having no date and are left out of any question that filters or groups by date.",
        })
    return expression, issues


def cast_and_recreate_table(con: duckdb.DuckDBPyConnection, table_name: str, col_types: dict[str, str]) -> List[dict]:
    """
    Alters table columns to their strongly typed versions in DuckDB.
    Returns the quality issues raised while converting (mixed date formats, values
    that could not be read), in the same shape the quality checks produce.
    """
    issues: List[dict] = []
    cast_exprs = []
    current_types = {
        row[0]: str(row[1]).upper() for row in con.execute(f'DESCRIBE "{table_name}"').fetchall()
    }

    for col, dtype in col_types.items():
        if dtype in ("DATE", "TIMESTAMP"):
            if current_types.get(col, "VARCHAR") == "VARCHAR":
                # Text dates: TRY_CAST alone reads only ISO and turns the rest to NULL.
                expression, col_issues = _convert_text_dates(con, table_name, col, dtype)
                issues.extend(col_issues)
                cast_exprs.append(f'{expression} AS "{col}"')
            else:
                cast_exprs.append(f'TRY_CAST("{col}" AS {dtype}) AS "{col}"')
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
    return issues
