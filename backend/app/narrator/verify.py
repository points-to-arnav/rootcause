import re
from typing import Any, Dict, List, Set, Tuple

NUMBER_REGEX = re.compile(r"(?<!\w)[$₹€£]?([0-9]+(?:,[0-9]{3})*(?:\.[0-9]+)?)([kKmMbB%]?)(?!\w)")

COMMON_YEARS = {2020, 2021, 2022, 2023, 2024, 2025, 2026, 2027, 2028, 2029, 2030}
COMMON_COUNTS = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 15, 20, 24, 30, 50, 100}

def parse_num_token(raw_num: str, suffix: str) -> float:
    cleaned = raw_num.replace(",", "")
    val = float(cleaned)
    s_lower = suffix.lower()
    if s_lower == "k":
        val *= 1_000
    elif s_lower == "m":
        val *= 1_000_000
    elif s_lower == "b":
        val *= 1_000_000_000
    return val

def extract_numbers_from_result(result: Dict[str, Any], derived: Dict[str, Any]) -> Set[float]:
    """Collects all valid numeric values from result rows and derived summaries."""
    valid_nums = set()

    # From rows
    for row in result.get("rows", []):
        for cell in row:
            if isinstance(cell, (int, float)) and cell == cell:
                valid_nums.add(round(float(cell), 2))
                valid_nums.add(round(abs(float(cell)), 2))

    # From derived
    for k, v in derived.items():
        if isinstance(v, (int, float)) and v == v:
            valid_nums.add(round(float(v), 2))
            valid_nums.add(round(abs(float(v)), 2))

    return valid_nums

def is_close_match(num: float, valid_nums: Set[float], rel_tol: float = 0.05) -> bool:
    """Checks if num is close to any valid number within tolerance."""
    if num in valid_nums:
        return True
    for v in valid_nums:
        if v == 0 and abs(num) < 0.1:
            return True
        if v != 0 and abs(num - v) / abs(v) <= rel_tol:
            return True
    return False

def verify_narrative(
    narrative: str,
    result: Dict[str, Any],
    derived: Dict[str, Any]
) -> Tuple[bool, List[str]]:
    """
    Verifies that numbers stated in narrative actually appear in result or derived fields.
    Returns (is_valid, list_of_unverified_tokens).
    """
    valid_nums = extract_numbers_from_result(result, derived)
    matches = NUMBER_REGEX.findall(narrative)
    unverified = []

    for num_str, suffix in matches:
        try:
            val = parse_num_token(num_str, suffix)
        except Exception:
            continue

        # Skip obvious calendar years and top-N ranking counters
        int_val = int(round(val))
        if int_val in COMMON_YEARS and not suffix:
            continue
        if int_val in COMMON_COUNTS and not suffix and val == int_val:
            continue

        # Check match
        if not is_close_match(val, valid_nums) and not is_close_match(round(val, 1), valid_nums):
            unverified.append(f"{num_str}{suffix}")

    return (len(unverified) == 0, unverified)
