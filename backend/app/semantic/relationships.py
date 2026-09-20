import re
from typing import Any, Dict, List, Tuple
import duckdb
from app.semantic.model import Relationship

def are_dtypes_compatible(t1: str, t2: str) -> bool:
    """Checks whether two column dtypes can form a foreign key join."""
    numeric_types = {"BIGINT", "DOUBLE"}
    if t1 in numeric_types and t2 in numeric_types:
        return True
    if t1 == "VARCHAR" and t2 == "VARCHAR":
        return True
    return False

def name_match_score(child_col: str, parent_table: str, parent_col: str) -> float:
    """Evaluates name matching score between child and parent key."""
    c_norm = child_col.lower().replace("_", "")
    p_col_norm = parent_col.lower().replace("_", "")
    p_tbl_norm = parent_table.lower().rstrip("s").replace("_", "")

    # Exact column name match (e.g. customer_id == customer_id)
    if c_norm == p_col_norm:
        return 1.0

    # Pattern match (e.g. customer_id == id in table customers)
    if (c_norm == f"{p_tbl_norm}id" or c_norm == f"{p_tbl_norm}code") and (p_col_norm in ["id", "code"]):
        return 0.9

    return 0.0

def detect_relationships(
    con: duckdb.DuckDBPyConnection,
    tables: Dict[str, Any]
) -> Tuple[List[Relationship], List[Dict[str, Any]]]:
    """
    Scans tables for candidate many-to-one relationships.
    Returns (relationships, orphan_key_dq_issues).
    """
    candidates: List[Relationship] = []
    orphan_issues: List[Dict[str, Any]] = []

    table_names = list(tables.keys())

    for c_tbl in table_names:
        c_cols = tables[c_tbl]["columns"]
        for p_tbl in table_names:
            if c_tbl == p_tbl:
                continue
            p_cols = tables[p_tbl]["columns"]
            p_rows = tables[p_tbl]["row_count"]
            if p_rows == 0:
                continue

            for c_col, c_meta in c_cols.items():
                for p_col, p_meta in p_cols.items():
                    # 1. Check dtype and name candidate match
                    if not are_dtypes_compatible(c_meta["dtype"], p_meta["dtype"]):
                        continue
                    n_score = name_match_score(c_col, p_tbl, p_col)
                    if n_score == 0.0:
                        continue

                    # 2. Check parent uniqueness
                    p_distinct = p_meta["distinct"]
                    p_null_cnt = p_meta["null_count"]
                    p_non_null = p_rows - p_null_cnt
                    if p_non_null == 0:
                        continue
                    p_uniqueness = p_distinct / p_non_null
                    parent_unique = (p_uniqueness >= 0.99)
                    if not parent_unique:
                        continue  # Must be unique parent key for many-to-one

                    # 3. Check containment in DuckDB
                    # Share of child's non-null values that exist in parent
                    containment_res = con.execute(f'''
                        SELECT 
                            COUNT(DISTINCT c."{c_col}") AS child_distinct,
                            COUNT(DISTINCT CASE WHEN p."{p_col}" IS NOT NULL THEN c."{c_col}" END) AS matched_distinct,
                            COUNT(*) AS child_rows,
                            COUNT(CASE WHEN p."{p_col}" IS NULL THEN 1 END) AS orphan_rows
                        FROM "{c_tbl}" AS c
                        LEFT JOIN "{p_tbl}" AS p ON c."{c_col}" = p."{p_col}"
                        WHERE c."{c_col}" IS NOT NULL
                    ''').fetchone()

                    c_distinct_val = containment_res[0]
                    matched_distinct = containment_res[1]
                    child_rows = containment_res[2]
                    orphan_rows = containment_res[3]

                    if c_distinct_val == 0:
                        continue

                    containment = matched_distinct / c_distinct_val

                    # Threshold: containment >= 0.90
                    if containment >= 0.90:
                        confidence = round(0.4 * n_score + 0.4 * containment + 0.2 * p_uniqueness, 2)
                        candidates.append(Relationship(
                            **{
                                "from": f"{c_tbl}.{c_col}",
                                "to": f"{p_tbl}.{p_col}",
                                "type": "many_to_one",
                                "confidence": confidence,
                                "containment": round(containment, 3),
                                "parent_unique": parent_unique,
                                "confirmed": False
                            }
                        ))

                        # Log orphan key DQ issue if orphan rows exist
                        if orphan_rows > 0:
                            pct = round((orphan_rows / child_rows) * 100, 2)
                            orphan_issues.append({
                                "id": f"dq_orphan_{c_tbl}_{c_col}",
                                "severity": "medium" if pct >= 1.0 else "low",
                                "type": "orphan_keys",
                                "table": c_tbl,
                                "column": c_col,
                                "count": orphan_rows,
                                "pct": pct,
                                "message": f"{orphan_rows} rows in '{c_tbl}.{c_col}' have no matching key in '{p_tbl}'.",
                                "impact": f"Rows whose {c_col} has no match in {p_tbl} appear under '(missing)' in breakdowns by {p_tbl} columns."
                            })

    # Keep only the highest confidence relationship per (from_col, parent_table)
    best_rels: Dict[str, Relationship] = {}
    for r in candidates:
        key = f"{r.from_col}->{r.to_col.split('.')[0]}"
        if key not in best_rels or r.confidence > best_rels[key].confidence:
            best_rels[key] = r

    return list(best_rels.values()), orphan_issues
