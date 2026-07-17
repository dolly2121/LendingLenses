"""Synthetic data generator for LendingLens. Never ingest anything external (Rules R3).

Deterministic: fixed seed, fixed "today" anchor, so `make data` run twice
produces byte-identical output regardless of the actual calendar date.
"""
import csv
import random
from datetime import date, timedelta
from pathlib import Path

SEED = 42
ROW_COUNT = 500
TODAY = date(2026, 7, 15)  # fixed anchor, not datetime.now(), for reproducibility

LANDING_DIR = Path(__file__).resolve().parent.parent / "data" / "landing"
TRANSCRIPTS_DIR = LANDING_DIR / "transcripts"

STATES = ["NSW", "VIC", "QLD", "WA", "SA", "TAS", "ACT", "NT"]
LOAN_TYPES = ["personal", "car", "home_improvement", "debt_consolidation", "business"]
STATUSES = ["approved", "pending", "declined"]
CHANNELS = ["direct", "broker"]
RATE_MIN, RATE_MAX = 5.5, 14.0
# Base rate per loan_type stands in for a risk_band that doesn't exist yet at Bronze
# (risk_band is derived later in Silver from loan_amount/loan_type, Phases.md Phase 3).
# Secured-ish loan types (car, home_improvement) sit lower; unsecured/variable-risk
# types (personal, debt_consolidation, business) sit higher, per typical AU non-bank rates.
BASE_RATE_BY_TYPE = {
    "car": 7.0,
    "home_improvement": 6.5,
    "debt_consolidation": 9.5,
    "personal": 10.0,
    "business": 9.0,
}
FIRST_NAMES = ["Sarah", "James", "Priya", "Liam", "Olivia", "Noah", "Mia", "Ethan",
               "Grace", "Lucas", "Chloe", "Mason", "Ava", "Jack", "Isla", "Ryan"]
LAST_NAMES = ["Mitchell", "Chen", "Nair", "Walker", "Bennett", "Ford", "Reid",
              "Nguyen", "Carter", "Hughes", "Patel", "Cooper", "Sharma", "Ellis"]

CSV_COLUMNS = ["loan_id", "customer_name", "state", "loan_amount", "loan_type",
               "interest_rate", "channel", "application_date", "loan_issue_date",
               "first_reimbursement_date", "status"]


def _synthetic_name(rng: random.Random) -> str:
    return f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}"


def _random_date(rng: random.Random, start: date, end: date) -> date:
    return start + timedelta(days=rng.randint(0, (end - start).days))


def _interest_rate(rng: random.Random, loan_type: str) -> float:
    rate = BASE_RATE_BY_TYPE[loan_type] + rng.uniform(-1.5, 2.5)
    return round(min(max(rate, RATE_MIN), RATE_MAX), 2)


def _loan_issue_date(rng: random.Random, application_date: date) -> date:
    return application_date + timedelta(days=rng.randint(1, 14))


def _first_reimbursement_date(rng: random.Random, loan_issue_date: date) -> date:
    return loan_issue_date + timedelta(days=rng.randint(28, 32))


def generate_rows() -> list[dict]:
    rng = random.Random(SEED)
    rows = []
    for i in range(1, ROW_COUNT + 1):
        loan_type = rng.choice(LOAN_TYPES)
        application_date = _random_date(rng, TODAY - timedelta(days=730), TODAY)
        loan_issue_date = _loan_issue_date(rng, application_date)
        first_reimbursement_date = _first_reimbursement_date(rng, loan_issue_date)
        rows.append({
            "loan_id": f"LOAN-{i:04d}",
            "customer_name": _synthetic_name(rng),
            "state": rng.choice(STATES),
            "loan_amount": round(rng.uniform(5000, 500000), 2),
            "loan_type": loan_type,
            "interest_rate": _interest_rate(rng, loan_type),
            "channel": rng.choice(CHANNELS),
            "application_date": application_date.isoformat(),
            "loan_issue_date": loan_issue_date.isoformat(),
            "first_reimbursement_date": first_reimbursement_date.isoformat(),
            "status": rng.choice(STATUSES),
        })

    # --- Planted defects, netting to exactly 6 quarantined rows (Phases.md Phase 1) ---
    # DEFECT 1 & 2: null state, LOAN-0050 and LOAN-0150 -> fails "state not null" (2 rows)
    rows[49]["state"] = ""
    rows[149]["state"] = ""
    # DEFECT 3: negative loan_amount, LOAN-0200 -> fails "amount between 0 and 5,000,000" (1 row)
    rows[199]["loan_amount"] = -1000.00
    # DEFECT 4: duplicate loan_id, LOAN-0300 rewritten to LOAN-0100 -> fails uniqueness (2 rows)
    rows[299]["loan_id"] = rows[99]["loan_id"]
    # DEFECT 5: future application_date, LOAN-0400 -> fails "not in the future" (1 row)
    rows[399]["application_date"] = (TODAY + timedelta(days=30)).isoformat()
    # Total: 2 + 1 + 2 + 1 = 6, matching Phase 1's arithmetic.

    return rows


def write_loans_csv(rows: list[dict]) -> Path:
    LANDING_DIR.mkdir(parents=True, exist_ok=True)
    out_path = LANDING_DIR / "loans_raw.csv"
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for row in rows:
            row = dict(row)
            row["loan_amount"] = f"{row['loan_amount']:.2f}"
            row["interest_rate"] = f"{row['interest_rate']:.2f}"
            writer.writerow(row)
    return out_path


TRANSCRIPTS = {
    # Normal enquiry: neutral tone, no hardship or complaint keywords.
    "normal_enquiry.txt": (
        "Customer: Priya Nair\n\n"
        "Hi, I'm calling to check the status of my personal loan application. "
        "I submitted it about a week ago and haven't heard back yet. "
        "Could you also confirm the current interest rate and repayment schedule? "
        "No rush, I just wanted an update. Thanks for your help."
    ),
    # Hardship call: clear hardship signals for nlp_flags.py keyword rules (Phase 6).
    "hardship_call.txt": (
        "Customer: Sarah Mitchell\n\n"
        "I'm calling because I lost my job last month and I'm really struggling to pay "
        "my loan repayments. I've fallen behind and I don't know what to do. "
        "Is there a hardship arrangement I can apply for? I can't afford the full "
        "repayment right now and I'm worried about what happens next. "
        "Any help you can offer would mean a lot."
    ),
    # Complaint call: clear complaint signals for nlp_flags.py keyword rules (Phase 6).
    "complaint_call.txt": (
        "Customer: James Chen\n\n"
        "I want to lodge a complaint about the fees charged on my account last month. "
        "This is completely unacceptable, nobody told me about these charges when I "
        "signed up and I feel misled. I've called twice already and nothing has been "
        "resolved. I want this escalated and I expect a call back today."
    ),
}


def write_transcripts() -> list[Path]:
    TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    paths = []
    for filename, content in TRANSCRIPTS.items():
        out_path = TRANSCRIPTS_DIR / filename
        out_path.write_text(content, encoding="utf-8", newline="\n")
        paths.append(out_path)
    return paths


def main() -> None:
    csv_path = write_loans_csv(generate_rows())
    transcript_paths = write_transcripts()
    print(f"loans_raw.csv: {ROW_COUNT} rows -> {csv_path}")
    print(f"transcripts: {len(transcript_paths)} files -> {TRANSCRIPTS_DIR}")


if __name__ == "__main__":
    main()
