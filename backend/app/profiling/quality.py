import re
from typing import Any, Dict, List, Optional
import duckdb

MEASURE_NAMES = re.compile(
    r"(quantity|qty|price|amount|cost|revenue|sales|units|stock|discount)",
    re.IGNORECASE
)

ID_NAMES = re.compile(
    r"(id|key|code|number|no)$",
    re.IGNORECASE
)

def run_quality_checks(con: duckdb.DuckDBPyConnection, table_name: str, profile: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Evaluates data quality checks for a table using its profile and DuckDB queries.
    Returns list of issue records:
    {id, severity, type, table, column, count, pct, message, impact}
    """
    issues = []
    row_count = profile["row_count"]
    if row_count == 0:
        return issues

    # 1. Duplicate rows check
    try:
        dupe_count = con.execute(f'''
            SELECT COUNT(*) - COUNT(DISTINCT *) FROM "{table_name}"
        ''').fetchone()[0]
        if dupe_count > 0:
            pct = round((dupe_count / row_count) * 100, 2)
            severity = "high" if pct >= 1.0 else "medium"
            issues.append({
                "id": f"dq_dupe_{table_name}",
                "severity": severity,
                "type": "duplicate_rows",
                "table": table_name,
                "column": None,
                "count": dupe_count,
                "pct": pct,
                "message": f"{dupe_count} duplicate rows ({pct}%) found in table '{table_name}'.",
                "impact": f"Duplicated rows are counted multiple times in sums and counts (about {pct}% of rows)."
            })
    except Exception:
        pass

    # Per-column checks
    cols = profile.get("columns", {})
    for col, cprof in cols.items():
        dtype = cprof["dtype"]
        null_count = cprof["null_count"]
        null_pct = cprof["null_pct"]
        distinct = cprof["distinct"]

        # 2. Missing values
        if null_count > 0:
            severity = "high" if null_pct >= 20.0 else ("medium" if null_pct >= 2.0 else "low")
            issues.append({
                "id": f"dq_null_{table_name}_{col}",
                "severity": severity,
                "type": "missing_values",
                "table": table_name,
                "column": col,
                "count": null_count,
                "pct": null_pct,
                "message": f"{null_pct}% of '{col}' values are missing ({null_count} rows).",
                "impact": f"Rows with no {col} appear under '(missing)' in breakdowns and are excluded from filters on it."
            })

        # 3. Duplicate IDs (only for the table's own primary key, e.g. 'sales_id', 'order_id' for sales, 'id')
        is_primary_id = (
            col == "id" or
            col == f"{table_name}_id" or
            col == f"{table_name.rstrip('s')}_id" or
            (table_name == "sales" and col == "order_id") or
            (table_name == "returns" and col == "return_id")
        )
        if is_primary_id and distinct < (row_count - null_count):
            dupe_id_count = (row_count - null_count) - distinct
            pct = round((dupe_id_count / row_count) * 100, 2)
            severity = "high" if pct >= 1.0 else "medium"
            issues.append({
                "id": f"dq_id_{table_name}_{col}",
                "severity": severity,
                "type": "duplicate_id",
                "table": table_name,
                "column": col,
                "count": dupe_id_count,
                "pct": pct,
                "message": f"Primary identifier '{col}' has {dupe_id_count} repeated values ({pct}%).",
                "impact": f"Repeated {col} values may double-count or cause fan-out in joined queries."
            })

        # 4. Negative values in measure columns
        if dtype in ["BIGINT", "DOUBLE"] and MEASURE_NAMES.search(col):
            try:
                neg_count = con.execute(f'''
                    SELECT COUNT(*) FROM "{table_name}" WHERE "{col}" < 0
                ''').fetchone()[0]
                if neg_count > 0:
                    pct = round((neg_count / row_count) * 100, 2)
                    issues.append({
                        "id": f"dq_neg_{table_name}_{col}",
                        "severity": "medium",
                        "type": "negative_values",
                        "table": table_name,
                        "column": col,
                        "count": neg_count,
                        "pct": pct,
                        "message": f"Column '{col}' has {neg_count} negative values.",
                        "impact": f"Negative values reduce aggregate totals; they may represent returns, adjustments, or errors."
                    })
            except Exception:
                pass

        # 5. Outliers (IQR x 3)
        if dtype in ["BIGINT", "DOUBLE"] and row_count >= 30:
            q1 = cprof.get("q1")
            q3 = cprof.get("q3")
            if q1 is not None and q3 is not None:
                iqr = q3 - q1
                if iqr > 0:
                    lower_b = q1 - 3 * iqr
                    upper_b = q3 + 3 * iqr
                    try:
                        outlier_res = con.execute(f'''
                            SELECT COUNT(*), COALESCE(SUM("{col}"), 0), MAX("{col}")
                            FROM "{table_name}"
                            WHERE "{col}" < ? OR "{col}" > ?
                        ''', (lower_b, upper_b)).fetchone()
                        outlier_count = outlier_res[0]
                        if outlier_count > 0:
                            max_val = outlier_res[2]
                            pct = round((outlier_count / row_count) * 100, 2)
                            issues.append({
                                "id": f"dq_outlier_{table_name}_{col}",
                                "severity": "medium" if pct >= 0.5 else "low",
                                "type": "outliers",
                                "table": table_name,
                                "column": col,
                                "count": outlier_count,
                                "pct": pct,
                                "message": f"{outlier_count} extreme outlier values found in '{col}'.",
                                "impact": f"Extreme values can skew totals and averages (largest value: {max_val})."
                            })
                    except Exception:
                        pass

        # 6. Constant column
        if distinct == 1 and row_count > 1:
            issues.append({
                "id": f"dq_const_{table_name}_{col}",
                "severity": "low",
                "type": "constant_column",
                "table": table_name,
                "column": col,
                "count": row_count,
                "pct": 100.0,
                "message": f"Column '{col}' contains only a single constant value.",
                "impact": f"'{col}' has zero variance and cannot explain differences across categories."
            })

    return issues
