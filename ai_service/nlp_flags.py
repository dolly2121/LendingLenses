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
EMI_QUERY_KEYWORDS = ["emi", "monthly instalment", "monthly installment", "instalment amount",
                      "installment amount", "how much do i owe", "minimum payment"]
ACCOUNT_UPDATE_KEYWORDS = ["update my address", "change my address", "update my details",
                           "change my details", "update my phone", "change my phone",
                           "update my email", "change of address", "account details"]
GENERAL_ENQUIRY_KEYWORDS = ["status of my", "check the status", "loan application",
                            "just wanted an update", "checking on", "any update on",
                            "interest rate", "repayment schedule"]

ENQUIRY_TYPE_COMPLAINT = "complaint"
ENQUIRY_TYPE_HARDSHIP = "hardship"
ENQUIRY_TYPE_EMI_QUERY = "emi_query"
ENQUIRY_TYPE_ACCOUNT_UPDATE = "account_update"
ENQUIRY_TYPE_GENERAL = "general_enquiry"
ENQUIRY_TYPE_OTHER = "other"

_NAME_PATTERN = re.compile(r"\b(" + "|".join(re.escape(n) for n in FIRST_NAMES + LAST_NAMES) + r")\b")


def sentiment_score(transcript: str) -> float:
    return _analyzer.polarity_scores(transcript)["compound"]


def hardship_flag(transcript: str) -> bool:
    lowered = transcript.lower()
    return any(keyword in lowered for keyword in HARDSHIP_KEYWORDS)


def complaint_flag(transcript: str) -> bool:
    lowered = transcript.lower()
    return any(keyword in lowered for keyword in COMPLAINT_KEYWORDS)


def classify_enquiry_type(transcript: str) -> str:
    """Keyword-based, same approach and honesty caveat as hardship_flag/
    complaint_flag - not general NLU. When multiple categories' keywords
    match, complaint and hardship take precedence over the others: they are
    the most sensitive/actionable categories for a lender, matching this
    project's existing hardship/complaint-first demo narrative.
    """
    lowered = transcript.lower()
    if any(keyword in lowered for keyword in COMPLAINT_KEYWORDS):
        return ENQUIRY_TYPE_COMPLAINT
    if any(keyword in lowered for keyword in HARDSHIP_KEYWORDS):
        return ENQUIRY_TYPE_HARDSHIP
    if any(keyword in lowered for keyword in EMI_QUERY_KEYWORDS):
        return ENQUIRY_TYPE_EMI_QUERY
    if any(keyword in lowered for keyword in ACCOUNT_UPDATE_KEYWORDS):
        return ENQUIRY_TYPE_ACCOUNT_UPDATE
    if any(keyword in lowered for keyword in GENERAL_ENQUIRY_KEYWORDS):
        return ENQUIRY_TYPE_GENERAL
    return ENQUIRY_TYPE_OTHER


def mask_names(transcript: str) -> str:
    """Redacts known synthetic name tokens with [NAME]."""
    return _NAME_PATTERN.sub("[NAME]", transcript)
