import os
import threading
from typing import Any, Dict, List, Optional, Tuple
import duckdb
from app.config import settings

def execute_query(
    db_path: str,
    sql: str,
    params: Tuple[Any, ...] = ()
) -> Dict[str, Any]:
    """
    Executes compiled SQL on read-only DuckDB connection.
    Enforces row cap and timeout watchdog interrupt.
    Returns:
    {
       "columns": list of column names,
       "rows": list of row tuples/lists (JSON-serializable),
       "row_count": int,
       "truncated": bool
    }
    """
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Database file not found: {db_path}")

    # Read-only connection
    con = duckdb.connect(db_path, read_only=True)

    # Watchdog timer to interrupt query if it exceeds timeout
    timed_out = False
    def interrupt():
        nonlocal timed_out
        timed_out = True
        try:
            con.interrupt()
        except Exception:
            pass

    watchdog = threading.Timer(settings.QUERY_TIMEOUT_S, interrupt)
    watchdog.start()

    try:
        cur = con.cursor()
        if params:
            cur.execute(sql, params)
        else:
            cur.execute(sql)

        col_names = [desc[0] for desc in cur.description] if cur.description else []
        rows = cur.fetchmany(settings.MAX_RESULT_ROWS + 1)

        truncated = len(rows) > settings.MAX_RESULT_ROWS
        if truncated:
            rows = rows[:settings.MAX_RESULT_ROWS]

        # Convert row values to JSON-safe primitives
        safe_rows = []
        for r in rows:
            safe_row = []
            for val in r:
                if val is None:
                    safe_row.append(None)
                elif isinstance(val, (int, float, bool, str)):
                    # Guard NaN/Inf
                    if isinstance(val, float) and (val != val or val == float("inf") or val == float("-inf")):
                        safe_row.append(None)
                    else:
                        safe_row.append(val)
                else:
                    safe_row.append(str(val))
            safe_rows.append(safe_row)

        return {
            "columns": col_names,
            "rows": safe_rows,
            "row_count": len(safe_rows),
            "truncated": truncated
        }

    except Exception as e:
        if timed_out:
            raise TimeoutError(f"Query timed out after {settings.QUERY_TIMEOUT_S}s.") from e
        raise e
    finally:
        watchdog.cancel()
        con.close()
