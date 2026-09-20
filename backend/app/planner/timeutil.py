from datetime import date, datetime, timedelta
import calendar
from typing import Optional, Tuple
from app.planner.plan_schema import Calendar, LastN, Between, AllTime, TimeRange, Comparison

def parse_iso_date(s: str) -> date:
    return datetime.strptime(s[:10], "%Y-%m-%d").date()

def add_months(d: date, months: int) -> date:
    month = d.month - 1 + months
    year = d.year + month // 12
    month = month % 12 + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)

def get_month_end(year: int, month: int) -> date:
    _, last_day = calendar.monthrange(year, month)
    return date(year, month, last_day)

def resolve_time_window(
    time_range: Optional[TimeRange],
    anchor_str: str,
    min_date_str: Optional[str] = None
) -> Tuple[date, date, str]:
    """
    Resolves TimeRange against anchor_date to half-open window [start, end)
    and returns (start_date, end_date, human_label).
    """
    anchor = parse_iso_date(anchor_str)

    if time_range is None or isinstance(time_range, AllTime):
        start = parse_iso_date(min_date_str) if min_date_str else date(2020, 1, 1)
        end = anchor + timedelta(days=1)
        return start, end, "All Time"

    if isinstance(time_range, LastN):
        unit = time_range.unit
        n = time_range.n

        if unit == "day":
            end = anchor + timedelta(days=1)
            start = anchor - timedelta(days=n - 1)
            return start, end, f"Last {n} days"

        elif unit == "month":
            # Check if anchor is month-end
            is_complete_month = (anchor.day == calendar.monthrange(anchor.year, anchor.month)[1])
            if is_complete_month:
                # Latest complete month ends on anchor + 1 day (1st of next month)
                end = add_months(date(anchor.year, anchor.month, 1), 1)
            else:
                # Exclude partial trailing month
                end = date(anchor.year, anchor.month, 1)

            start = add_months(end, -n)
            label = f"Last {n} month{'s' if n > 1 else ''}"
            return start, end, label

        elif unit == "year":
            is_complete_year = (anchor.month == 12 and anchor.day == 31)
            end_year = anchor.year + 1 if is_complete_year else anchor.year
            end = date(end_year, 1, 1)
            start = date(end_year - n, 1, 1)
            return start, end, f"Last {n} year{'s' if n > 1 else ''}"

        else:
            # Fallback week/quarter
            end = anchor + timedelta(days=1)
            start = anchor - timedelta(days=n * 30)
            return start, end, f"Last {n} {unit}s"

    if isinstance(time_range, Calendar):
        val = time_range.value.strip()
        unit = time_range.unit

        if unit == "month":
            parts = val.split("-")
            year, month = int(parts[0]), int(parts[1])
            start = date(year, month, 1)
            end = add_months(start, 1)
            label = start.strftime("%b %Y")
            return start, end, label

        elif unit == "year":
            year = int(val)
            start = date(year, 1, 1)
            end = date(year + 1, 1, 1)
            label = str(year)
            return start, end, label

        elif unit == "quarter":
            year = int(val[:4])
            q = int(val[-1])
            start_m = (q - 1) * 3 + 1
            start = date(year, start_m, 1)
            end = add_months(start, 3)
            label = f"Q{q} {year}"
            return start, end, label

    if isinstance(time_range, Between):
        start = time_range.start
        end = time_range.end + timedelta(days=1)
        label = f"{start} to {time_range.end}"
        return start, end, label

    # Default
    return anchor - timedelta(days=30), anchor + timedelta(days=1), "Past Month"

def resolve_comparison_window(
    start: date,
    end: date,
    comp_type: str = "previous_period"
) -> Tuple[date, date, str]:
    """
    Computes baseline comparison window for previous_period or previous_year.
    """
    if comp_type == "previous_year":
        b_start = add_months(start, -12)
        b_end = add_months(end, -12)
        label = "Previous Year"
        return b_start, b_end, label

    # Previous period
    # Check if month-aligned
    is_month_aligned = (start.day == 1 and end.day == 1)
    if is_month_aligned:
        month_diff = (end.year - start.year) * 12 + (end.month - start.month)
        b_start = add_months(start, -month_diff)
        b_end = start
        b_label = "Previous Period"
        if month_diff == 1:
            b_label = b_start.strftime("%b %Y")
        return b_start, b_end, b_label

    days_diff = (end - start).days
    b_start = start - timedelta(days=days_diff)
    b_end = start
    return b_start, b_end, "Previous Period"
