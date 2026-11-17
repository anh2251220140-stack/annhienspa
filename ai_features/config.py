"""Opt-in AI configuration; never reads or modifies a dotenv file."""
import os
import math
from contextlib import contextmanager
from contextvars import ContextVar
from time import monotonic

from django.conf import settings

deadline = ContextVar("ai_deadline", default=None)
GEMINI_MIN_TIMEOUT_MS = 10000
GEMINI_REQUEST_TIMEOUT_MS = 12000
GEMINI_TOTAL_SECONDS = 40.0


def gemini_timeout_ms(seconds, requested_ms=GEMINI_REQUEST_TIMEOUT_MS):
    """Allocate within an existing deadline; never enlarge it to Google's minimum."""
    if (type(requested_ms) is not int or requested_ms < GEMINI_MIN_TIMEOUT_MS
            or not math.isfinite(seconds)):
        raise TimeoutError("Invalid Gemini timeout allocation")
    # Reserve local setup/validation overhead instead of rounding a short budget up.
    # SDK serializes X-Server-Timeout with ceil(seconds). Whole seconds keep
    # Google's server deadline from rounding past the application's remainder.
    available = math.floor(seconds - 0.25) * 1000
    result = min((requested_ms // 1000) * 1000, available)
    if result < GEMINI_MIN_TIMEOUT_MS:
        raise TimeoutError("Insufficient remaining budget for Gemini")
    return result


def check_gemini_deadline(request, seconds):
    """HTTPX pre-send hook: also catch slow client setup/SDK serialization."""
    try:
        value = float(request.headers.get("X-Server-Timeout", "0"))
    except (TypeError, ValueError):
        raise TimeoutError("Invalid Gemini server deadline") from None
    if not math.isfinite(value) or value < 10 or value > seconds:
        raise TimeoutError("Gemini deadline exceeds remaining allocation")


def option(name, default=None):
    return getattr(settings, name, os.environ.get(name, default))


def enabled(name):
    return str(option(name, "false")).lower() == "true"


@contextmanager
def time_budget(*, provider=None):
    if (provider or option("AI_PROVIDER", "mock")) == "gemini":
        seconds = min(GEMINI_TOTAL_SECONDS, float(option("AI_GEMINI_TIMEOUT_SECONDS", GEMINI_TOTAL_SECONDS)))
    else:
        seconds = min(8.0, float(option("AI_TIMEOUT_SECONDS", 8)))
    if not math.isfinite(seconds) or seconds <= 0:
        raise TimeoutError("Invalid AI time budget")
    value = monotonic() + seconds
    parent = deadline.get()
    token = deadline.set(min(parent, value) if parent is not None else value)
    try:
        yield
    finally:
        deadline.reset(token)


def remaining():
    value = deadline.get()
    seconds = 8 if value is None else value - monotonic()
    if seconds <= 0:
        raise TimeoutError("AI deadline exceeded")
    return seconds
