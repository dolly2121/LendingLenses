import polars as pl

from pipeline.silver import _build_silver_loans, mask_name

RAW_NAME = "Alice Smith"


def test_same_name_gives_same_hash():
    assert mask_name(RAW_NAME) == mask_name(RAW_NAME)


def test_different_names_give_different_hashes():
    assert mask_name("Alice Smith") != mask_name("Bob Jones")


def test_hash_is_not_the_raw_name():
    assert mask_name(RAW_NAME) != RAW_NAME
    assert RAW_NAME not in mask_name(RAW_NAME)


def test_no_raw_name_survives_into_silver():
    good = pl.DataFrame([{
        "loan_id": "LOAN-0001", "customer_name": RAW_NAME, "state": "NSW",
        "loan_amount": 10_000.0, "loan_type": "personal", "interest_rate": 7.5,
        "channel": "direct", "application_date": "2026-01-01", "status": "approved",
    }])
    silver = _build_silver_loans(good)

    assert "customer_name" not in silver.columns
    assert "customer_ref_hash" in silver.columns
    assert silver["customer_ref_hash"][0] == mask_name(RAW_NAME)
    for col in silver.columns:
        if silver[col].dtype == pl.Utf8:
            assert RAW_NAME not in silver[col].to_list()
