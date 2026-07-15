"""Keyword-based NLP flags and masking for the AI service (Phases.md Phase 6).

Explainable beats clever in a risk context (Architecture.md section 3): VADER
sentiment plus keyword rules, not a trained classifier. Name masking is a
keyword match against the same synthetic name pool generate_data.py draws
from - NOT general NER, and only proven to work against the 3 official
transcripts (Rules R3a). Never feed this an arbitrary or audience-suggested
transcript.
"""
import re

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from pipeline.generate_data import FIRST_NAMES, LAST_NAMES

_analyzer = SentimentIntensityAnalyzer()

HARDSHIP_KEYWORDS = ["hardship", "lost my job", "struggling", "fallen behind", "can't afford"]
COMPLAINT_KEYWORDS = ["complaint", "unacceptable", "misled", "escalate"]

_NAME_PATTERN = re.compile(r"\b(" + "|".join(re.escape(n) for n in FIRST_NAMES + LAST_NAMES) + r")\b")


def sentiment_score(transcript: str) -> float:
    return _analyzer.polarity_scores(transcript)["compound"]


def hardship_flag(transcript: str) -> bool:
    lowered = transcript.lower()
    return any(keyword in lowered for keyword in HARDSHIP_KEYWORDS)


def complaint_flag(transcript: str) -> bool:
    lowered = transcript.lower()
    return any(keyword in lowered for keyword in COMPLAINT_KEYWORDS)


def mask_names(transcript: str) -> str:
    """Redacts known synthetic name tokens with [NAME]."""
    return _NAME_PATTERN.sub("[NAME]", transcript)
