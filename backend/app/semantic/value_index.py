import re
import unicodedata
from typing import Any, Dict, List, Optional
from rapidfuzz import fuzz, process
from app.semantic.model import Metric, TableMeta

def normalize_text(text: str) -> str:
    s = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode("ascii")
    s = s.lower().strip()
    s = re.sub(r"[^\w\s]", "", s)
    s = re.sub(r"\s+", " ", s)
    return s

class ValueIndex:
    def __init__(self):
        # List of indexed entries:
        # { "term_normalized": str, "display_term": str, "kind": "value"|"column"|"metric", "target": str, "canonical_value": Any }
        self.entries: List[Dict[str, Any]] = []
        self._term_lookup: Dict[str, List[Dict[str, Any]]] = {}

    def build(self, tables: Dict[str, TableMeta], metrics: List[Metric]):
        self.entries = []
        self._term_lookup = {}

        # 1. Index metric names and synonyms
        for m in metrics:
            all_terms = [m.name, m.label] + m.synonyms
            for term in all_terms:
                norm = normalize_text(term)
                if norm:
                    entry = {
                        "term_normalized": norm,
                        "display_term": term,
                        "kind": "metric",
                        "target": m.name,
                        "canonical_value": m.name
                    }
                    self.entries.append(entry)
                    self._term_lookup.setdefault(norm, []).append(entry)

        # 2. Index table & column names
        for tbl_name, tmeta in tables.items():
            t_norm = normalize_text(tmeta.display_name)
            if t_norm:
                entry = {
                    "term_normalized": t_norm,
                    "display_term": tmeta.display_name,
                    "kind": "table",
                    "target": tbl_name,
                    "canonical_value": tbl_name
                }
                self.entries.append(entry)
                self._term_lookup.setdefault(t_norm, []).append(entry)

            for col_name, cmeta in tmeta.columns.items():
                c_norm = normalize_text(cmeta.display_name)
                if c_norm:
                    entry = {
                        "term_normalized": c_norm,
                        "display_term": cmeta.display_name,
                        "kind": "column",
                        "target": f"{tbl_name}.{col_name}",
                        "canonical_value": f"{tbl_name}.{col_name}"
                    }
                    self.entries.append(entry)
                    self._term_lookup.setdefault(c_norm, []).append(entry)

                # 3. Index sample values of dimension & entity columns
                if cmeta.role == "dimension" or cmeta.entity:
                    for val in cmeta.samples:
                        if val is not None and str(val).strip():
                            v_norm = normalize_text(str(val))
                            if v_norm and len(v_norm) >= 2:
                                entry = {
                                    "term_normalized": v_norm,
                                    "display_term": str(val),
                                    "kind": "value",
                                    "target": f"{tbl_name}.{col_name}",
                                    "canonical_value": val
                                }
                                self.entries.append(entry)
                                self._term_lookup.setdefault(v_norm, []).append(entry)

    def search_question(self, question: str, score_threshold: float = 85.0) -> List[Dict[str, Any]]:
        """
        Extracts 1-3 word n-grams from the question and finds matching candidate terms.
        Returns sorted list of matches: {term, kind, target, value, score}.
        """
        words = normalize_text(question).split()
        ngrams = []
        n_len = len(words)

        for size in [1, 2, 3]:
            for i in range(n_len - size + 1):
                ngrams.append(" ".join(words[i : i + size]))

        unique_ngrams = list(set(ngrams))
        terms_corpus = list(self._term_lookup.keys())

        matches = []
        seen_targets = set()

        for ng in unique_ngrams:
            # 1. Exact match
            if ng in self._term_lookup:
                for entry in self._term_lookup[ng]:
                    t_key = f"{entry['kind']}:{entry['target']}:{entry['canonical_value']}"
                    if t_key not in seen_targets:
                        seen_targets.add(t_key)
                        matches.append({
                            "term": ng,
                            "kind": entry["kind"],
                            "target": entry["target"],
                            "value": entry["canonical_value"],
                            "score": 100.0
                        })
                continue

            # 2. Fuzzy match
            best_results = process.extract(
                ng,
                terms_corpus,
                scorer=fuzz.WRatio,
                score_cutoff=score_threshold,
                limit=3
            )
            for match_term, score, _ in best_results:
                for entry in self._term_lookup[match_term]:
                    t_key = f"{entry['kind']}:{entry['target']}:{entry['canonical_value']}"
                    if t_key not in seen_targets:
                        seen_targets.add(t_key)
                        matches.append({
                            "term": ng,
                            "matched_term": entry["display_term"],
                            "kind": entry["kind"],
                            "target": entry["target"],
                            "value": entry["canonical_value"],
                            "score": round(score, 1)
                        })

        return sorted(matches, key=lambda x: x["score"], reverse=True)
