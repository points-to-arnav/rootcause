import re
from typing import Any, Dict, List
import duckdb

SENSITIVE_PATTERN = re.compile(
    r"(email|phone|mobile|address|ssn|aadhaar|pan|password|passport|iban|card)",
    re.IGNORECASE
)

def is_sensitive_column(col_name: str) -> bool:
    """Returns True if column name implies PII/sensitive data that should not be sampled."""
    return bool(SENSITIVE_PATTERN.search(col_name))

def profile_table(con: duckdb.DuckDBPyConnection, table_name: str, col_types: Dict[str, str]) -> Dict[str, Any]:
    """
    Profiles all columns of table_name using read-only DuckDB queries.
    Returns dictionary of column statistics.
    """
    # Total row count
    row_count = con.execute(f'SELECT COUNT(*) FROM "{table_name}"').fetchone()[0]
    if row_count == 0:
        return {"row_count": 0, "columns": {}}

    col_profiles = {}

    for col, dtype in col_types.items():
        # Basic stats: nulls, distinct
        stats = con.execute(f'''
            SELECT 
                COUNT(*) - COUNT("{col}") AS null_count,
                COUNT(DISTINCT "{col}") AS distinct_count,
                MIN("{col}") AS min_val,
                MAX("{col}") AS max_val
            FROM "{table_name}"
        ''').fetchone()

        null_count = stats[0]
        distinct_count = stats[1]
        min_val = stats[2]
        max_val = stats[3]

        null_pct = round((null_count / row_count) * 100, 2)
        distinct_ratio = round((distinct_count / row_count), 4)

        prof = {
            "dtype": dtype,
            "null_count": null_count,
            "null_pct": null_pct,
            "distinct": distinct_count,
            "distinct_ratio": distinct_ratio,
            "min": str(min_val) if min_val is not None else None,
            "max": str(max_val) if max_val is not None else None,
            "top_values": [],
            "samples": []
        }

        # Numeric stats: mean, std, quartiles
        if dtype in ["BIGINT", "DOUBLE"] and distinct_count > 0:
            try:
                num_stats = con.execute(f'''
                    SELECT 
                        AVG("{col}"),
                        STDDEV_SAMP("{col}"),
                        quantile_cont("{col}", 0.25),
                        quantile_cont("{col}", 0.75)
                    FROM "{table_name}"
                    WHERE "{col}" IS NOT NULL
                ''').fetchone()
                prof["mean"] = round(num_stats[0], 2) if num_stats[0] is not None else None
                prof["std"] = round(num_stats[1], 2) if num_stats[1] is not None else None
                prof["q1"] = round(num_stats[2], 2) if num_stats[2] is not None else None
                prof["q3"] = round(num_stats[3], 2) if num_stats[3] is not None else None
            except Exception:
                pass

        # Top values (top 5)
        try:
            top_rows = con.execute(f'''
                SELECT CAST("{col}" AS VARCHAR) AS val, COUNT(*) AS cnt
                FROM "{table_name}"
                WHERE "{col}" IS NOT NULL
                GROUP BY 1
                ORDER BY cnt DESC
                LIMIT 5
            ''').fetchall()
            prof["top_values"] = [{"value": r[0][:40], "count": r[1]} for r in top_rows]
        except Exception:
            prof["top_values"] = []

        # Samples (up to 5 distinct values; suppressed if sensitive)
        if is_sensitive_column(col):
            prof["samples"] = []
            prof["is_sensitive"] = True
        else:
            prof["is_sensitive"] = False
            prof["samples"] = [r["value"] for r in prof["top_values"]]

        col_profiles[col] = prof

    return {
        "row_count": row_count,
        "columns": col_profiles
    }
