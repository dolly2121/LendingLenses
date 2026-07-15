import polars as pl

from pipeline.silver import _validate_loans

VALID_ROW = {
    "loan_id": "LOAN-0001", "customer_name": "Alice Smith", "state": "NSW",
    "loan_amount": 10_000.0, "loan_type": "personal", "application_date": "2026-01-01",
    "status": "approved",
}


def _df(*overrides: dict) -> pl.DataFrame:
    rows = [VALID_ROW | o for o in overrides] if overrides else [VALID_ROW]
    return pl.DataFrame(rows)


def test_valid_rows_pass_untouched():
    df = _df({"loan_id": "LOAN-0001"}, {"loan_id": "LOAN-0002"})
    bad_indices, quarantine_rows, fail_counts = _validate_loans(df)
    assert bad_indices == set()
    assert quarantine_rows == []
    assert all(count == 0 for count in fail_counts.values())


def test_negative_amount_quarantined():
    df = _df({"loan_amount": -1000.0})
    bad_indices, quarantine_rows, fail_counts = _validate_loans(df)
    assert bad_indices == {0}
    assert quarantine_rows[0]["check_name"] == "loan_amount_range"
    assert fail_counts["loan_amount_range"] == 1


def test_null_state_quarantined():
    # Two rows, not one: pandera's polars backend omits the row index when
    # *every* row fails a not_nullable check, a path the real 500-row batch
    # never hits (defects are always a small fraction of the batch).
    df = _df({"loan_id": "LOAN-0001", "state": "NSW"}, {"loan_id": "LOAN-0002", "state": None})
    bad_indices, quarantine_rows, fail_counts = _validate_loans(df)
    assert bad_indices == {1}
    assert quarantine_rows[0]["check_name"] == "state_not_null"
    assert fail_counts["state_not_null"] == 1


def test_duplicate_loan_id_flags_both_rows():
    df = _df({"loan_id": "LOAN-0001"}, {"loan_id": "LOAN-0001"})
    bad_indices, quarantine_rows, fail_counts = _validate_loans(df)
    assert bad_indices == {0, 1}
    assert len(quarantine_rows) == 2
    assert all(r["check_name"] == "loan_id_unique" for r in quarantine_rows)
    assert fail_counts["loan_id_unique"] == 2


def test_future_date_quarantined():
    df = _df({"application_date": "2099-01-01"})
    bad_indices, quarantine_rows, fail_counts = _validate_loans(df)
    assert bad_indices == {0}
    assert quarantine_rows[0]["check_name"] == "application_date_not_future"
    assert fail_counts["application_date_not_future"] == 1


def test_quarantine_row_never_carries_the_full_raw_row():
    df = _df({"customer_name": "Alice Smith", "loan_amount": -1000.0})
    _, quarantine_rows, _ = _validate_loans(df)
    row = quarantine_rows[0]
    assert set(row) == {"source_table", "source_row_id", "offending_field",
                         "offending_value", "check_name", "reason"}
    assert "Alice Smith" not in row.values()
