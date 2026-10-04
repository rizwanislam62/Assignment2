"""Field-level validation. Regexes check identifier *format* only;
numeric ranges are checked with ordinary comparisons."""
import math
import re

from .exceptions import InvalidIdentifierError, InvalidRecordError

PARTICIPANT_ID_RE = re.compile(r"^P\d{3}$")
SESSION_ID_RE = re.compile(r"^FIT-\d{4}-\d{3}$")

# Documented plausible ranges (inclusive) for measurements.
RANGES = {
    "heart_rate": (30, 220),          # beats per minute
    "skin_response": (0, 50),         # simulated sensor units, non-negative
    "temperature": (25, 42),          # skin temperature, degrees C
    "activity_level": (0, 1),
    "signal_quality": (0, 1),
    "baseline_heart_rate": (30, 120),
    "baseline_skin_response": (0, 50),
    "baseline_temperature": (25, 42),
}


def validate_participant_id(value):
    if not PARTICIPANT_ID_RE.fullmatch(value):
        raise InvalidIdentifierError("participant_id", value, "P followed by three digits")
    return value


def validate_session_id(value):
    if not SESSION_ID_RE.fullmatch(value):
        raise InvalidIdentifierError("session_id", value, "FIT-YYYY-NNN")
    return value


def parse_number(field, raw, integer=False):
    """Convert text to int/float, rejecting blanks, junk, NaN and infinity."""
    if raw == "":
        raise InvalidRecordError([(field, "missing value")])
    try:
        value = int(raw) if integer else float(raw)
    except ValueError:
        kind = "an integer" if integer else "a number"
        raise InvalidRecordError([(field, f"{raw!r} is not {kind}")]) from None
    if not math.isfinite(value):
        raise InvalidRecordError([(field, f"{raw!r} is not a finite number")])
    return value


def check_range(field, value):
    lo, hi = RANGES[field]
    if not lo <= value <= hi:
        raise InvalidRecordError([(field, f"{value} is outside allowed range {lo} to {hi}")])
    return value
