from typing import Any, Dict, List, Optional, Tuple
import duckdb
from app.semantic.model import Relationship, TableMeta, TimeInfo

class JoinGraph:
    def __init__(self, tables: Dict[str, TableMeta], relationships: List[Relationship]):
        self.tables = tables
        self.relationships = relationships
        # Directed graph: child_table -> list of (parent_table, child_col, parent_col)
        self.adj: Dict[str, List[Tuple[str, str, str]]] = {t: [] for t in tables}
        for rel in relationships:
            c_tbl, c_col = rel.from_col.split(".")
            p_tbl, p_col = rel.to_col.split(".")
            if c_tbl in self.adj:
                self.adj[c_tbl].append((p_tbl, c_col, p_col))

    def pick_fact_table(self) -> str:
        """
        Picks the primary fact table:
        The table with the most rows that has at least one time column, at least one measure,
        and is child in at least one relationship.
        """
        best_table = None
        max_score = -1

        for tbl_name, tmeta in self.tables.items():
            has_time = any(c.role == "time" for c in tmeta.columns.values())
            has_measure = any(c.role == "measure" for c in tmeta.columns.values())
            outgoing_edges = len(self.adj.get(tbl_name, []))

            # Score prioritizes having time + measures + rows
            score = tmeta.row_count
            if has_time:
                score *= 2
            if has_measure:
                score *= 2
            score += outgoing_edges * 1000

            if score > max_score:
                max_score = score
                best_table = tbl_name

        return best_table or list(self.tables.keys())[0]

    def get_time_info(self, con: duckdb.DuckDBPyConnection, fact_table: str) -> TimeInfo:
        """Derives time range and anchor_date (= max date of primary time column)."""
        tmeta = self.tables.get(fact_table)
        if not tmeta:
            return TimeInfo()

        # Find primary time column (e.g. order_date)
        time_col = None
        for cname, cmeta in tmeta.columns.items():
            if cmeta.role == "time":
                time_col = f"{fact_table}.{cname}"
                break

        if not time_col:
            return TimeInfo()

        tbl, col = time_col.split(".")
        try:
            row = con.execute(f'SELECT MIN("{col}"), MAX("{col}") FROM "{tbl}" WHERE "{col}" IS NOT NULL').fetchone()
            min_date = str(row[0])[:10] if row[0] else None
            max_date = str(row[1])[:10] if row[1] else None
            return TimeInfo(
                primary_column=time_col,
                min=min_date,
                max=max_date,
                anchor_date=max_date  # Critical: Anchored to data max date!
            )
        except Exception:
            return TimeInfo(primary_column=time_col)

    def find_join_path(self, start_table: str, target_table: str) -> Optional[List[Tuple[str, str, str, str]]]:
        """
        Finds shortest path of many-to-one joins from start_table to target_table using BFS.
        Returns list of (from_tbl, from_col, to_tbl, to_col).
        """
        if start_table == target_table:
            return []

        queue = [(start_table, [])]
        visited = {start_table}

        while queue:
            curr_tbl, path = queue.pop(0)
            if curr_tbl == target_table:
                return path

            for p_tbl, c_col, p_col in self.adj.get(curr_tbl, []):
                if p_tbl not in visited:
                    visited.add(p_tbl)
                    new_path = path + [(curr_tbl, c_col, p_tbl, p_col)]
                    queue.append((p_tbl, new_path))

        return None
