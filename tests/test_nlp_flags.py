from pathlib import Path

from ai_service.nlp_flags import complaint_flag, hardship_flag, mask_names
from pipeline.generate_data import FIRST_NAMES, LAST_NAMES

TRANSCRIPTS_DIR = Path(__file__).resolve().parent.parent / "data" / "landing" / "transcripts"


def _read(name: str) -> str:
    return (TRANSCRIPTS_DIR / name).read_text(encoding="utf-8")


def test_hardship_transcript_flags_hardship_only():
    text = _read("hardship_call.txt")
    assert hardship_flag(text) is True
    assert complaint_flag(text) is False


def test_complaint_transcript_flags_complaint_only():
    text = _read("complaint_call.txt")
    assert complaint_flag(text) is True
    assert hardship_flag(text) is False


def test_normal_transcript_flags_neither():
    text = _read("normal_enquiry.txt")
    assert hardship_flag(text) is False
    assert complaint_flag(text) is False


def test_masking_removes_name_tokens_from_all_three_official_transcripts():
    # Not general NER (Rules R3a): only proven against these 3 transcripts.
    names = set(FIRST_NAMES) | set(LAST_NAMES)
    for filename in ("hardship_call.txt", "complaint_call.txt", "normal_enquiry.txt"):
        masked = mask_names(_read(filename))
        found = names & set(masked.replace(",", "").replace(".", "").split())
        assert found == set(), f"{filename} still contains raw name token(s): {found}"
        assert "[NAME]" in masked
