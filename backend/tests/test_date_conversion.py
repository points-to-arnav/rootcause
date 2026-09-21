from collections import Counter
from datetime import date, datetime
from pathlib import Path

import duckdb
import pandas as pd
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.profiling.types import cast_and_recreate_table

SAMPLE_XLSX = Path(__file__).resolve().parents[2] / "sample_data" / "retail_demo.xlsx"


def _convert(values, dtype="DATE"):
    """Runs the real cast over a one-column text table; returns (dates, issues)."""
    frame = pd.DataFrame({"d": pd.Series(values, dtype=object)})
    con = duckdb.connect()
    con.register("frame", frame)
    con.execute('CREATE TABLE t AS SELECT * FROM frame')
    issues = cast_and_recreate_table(con, "t", {"d": dtype})
    return [row[0] for row in con.execute('SELECT d FROM t').fetchall()], issues


def test_day_first_text_dates_are_recovered_next_to_iso_dates():
    dates, issues = _convert(["2025-01-02", "16/01/2025", "03/02/2025"])

    # 16/01 can only be day-first, so 03/02 is read the same way: 3 February.
    assert dates == [date(2025, 1, 2), date(2025, 1, 16), date(2025, 2, 3)]
    assert [i["type"] for i in issues] == ["inconsistent_dates"]
    assert issues[0]["count"] == 2
    assert "day-first" in issues[0]["impact"]


def test_month_first_is_chosen_when_a_second_part_exceeds_twelve():
    dates, issues = _convert(["01/16/2025", "02/03/2025"])

    # 01/16 can only be month-first, so 02/03 is read MM/DD too: 3 February.
    assert dates == [date(2025, 1, 16), date(2025, 2, 3)]
    assert issues == []  # one consistent format, order settled: nothing to warn about


def test_month_first_is_named_in_the_warning_when_formats_are_mixed():
    dates, issues = _convert(["2025-01-02", "01/16/2025", "02/03/2025"])

    assert dates == [date(2025, 1, 2), date(2025, 1, 16), date(2025, 2, 3)]
    assert "month-first" in issues[0]["impact"]


def test_ambiguous_dates_default_to_day_first_and_say_so():
    dates, issues = _convert(["01/02/2025", "03/04/2025"])

    assert dates == [date(2025, 2, 1), date(2025, 4, 3)]
    assert "assumed" in issues[0]["impact"]


def test_unreadable_values_become_null_and_are_reported_not_dropped():
    dates, issues = _convert(["2025-01-02", "not a date", "2025-01-04"])

    assert dates == [date(2025, 1, 2), None, date(2025, 1, 4)]
    invalid = [i for i in issues if i["type"] == "invalid_values"]
    assert len(invalid) == 1 and invalid[0]["count"] == 1


def test_a_column_uniformly_in_one_clear_format_is_converted_without_a_warning():
    """Every value DD-MM-YYYY, order settled by 16-01: a format, not a data problem."""
    dates, issues = _convert(["01-01-2025", "16-01-2025", "31-10-2025"])

    assert dates == [date(2025, 1, 1), date(2025, 1, 16), date(2025, 10, 31)]
    assert issues == []


def test_iso_only_column_raises_no_issue():
    dates, issues = _convert(["2025-01-02", "2025-03-04"])

    assert dates == [date(2025, 1, 2), date(2025, 3, 4)]
    assert issues == []


def test_native_date_column_is_untouched_and_raises_no_issue():
    frame = pd.DataFrame({"d": [date(2025, 1, 2), date(2025, 3, 4)]})
    con = duckdb.connect()
    con.register("frame", frame)
    con.execute("CREATE TABLE t AS SELECT * FROM frame")

    assert cast_and_recreate_table(con, "t", {"d": "DATE"}) == []
    assert [r[0] for r in con.execute("SELECT d FROM t").fetchall()] == [date(2025, 1, 2), date(2025, 3, 4)]


def test_timestamp_text_dates_keep_the_time_part():
    dates, _ = _convert(["2025-01-02 10:30:00", "16/01/2025 08:15:00"], dtype="TIMESTAMP")

    assert [d.isoformat() for d in dates] == ["2025-01-02T10:30:00", "2025-01-16T08:15:00"]


def test_sample_dataset_keeps_every_order_date_and_matches_pandas_revenue():
    """The demo file plants ~2% DD/MM/YYYY text dates; none may be lost."""
    client = TestClient(app)
    response = client.post("/api/datasets/sample")
    assert response.status_code == 200

    raw = pd.read_excel(SAMPLE_XLSX, sheet_name="Sales", dtype=object)
    # Independent of the app's parser: native cells as they are, text cells strictly dd/mm/yyyy.
    expected = Counter(
        (order_id, datetime.strptime(v, "%d/%m/%Y").date() if isinstance(v, str) else pd.Timestamp(v).date())
        for order_id, v in zip(raw["order_id"], raw["order_date"])
    )

    con = duckdb.connect(str(Path(settings.DATA_DIR) / "ds_retail_sample" / "data.duckdb"), read_only=True)
    try:
        rows, null_dates, total = con.execute(
            "SELECT COUNT(*), COUNT(*) FILTER (WHERE order_date IS NULL), SUM(amount) FROM sales"
        ).fetchone()
        actual = Counter(con.execute("SELECT order_id, order_date FROM sales").fetchall())
    finally:
        con.close()

    assert rows == len(raw)
    assert null_dates == 0
    assert abs(total - pd.to_numeric(raw["amount"]).sum()) < 0.01
    assert actual == expected
