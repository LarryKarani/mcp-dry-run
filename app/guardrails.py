"""Defense-in-depth guardrails. Pure functions, easy to unit test.

Three layers, each independently testable:

* Layer 1 — `validate_input`: clamps length, strips control chars, refuses
  obviously malformed input BEFORE the LLM ever sees it.
* Layer 2 — system prompt secrecy clauses live in `prompts/system_v3.md`.
  This module exposes `looks_like_prompt_leak` so callers can sanity-check.
* Layer 3 — `validate_output`: blocks outputs that leak the system prompt,
  claim a different identity, or echo secret-shaped strings. Replaces
  blocked content with a generic safe message.

The agent wires layers 1 and 3 around every turn. Layer 2 is enforced by
the prompt itself; the only thing this file does for layer 2 is provide
the leak detector that backs layer 3.
"""
from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass

from app.config import get_settings

log = logging.getLogger(__name__)

SAFE_REFUSAL = (
    "Sorry — I can only help with Meridian Electronics product browsing, "
    "order placement, and order history lookup. Is there something in that area I can help with?"
)

OUTPUT_BLOCKED_FALLBACK = (
    "Sorry, I can't share that. I can help with browsing Meridian Electronics "
    "products, verifying your account, placing an order, or looking up your order history."
)

# Phrases that should never appear in a user-facing message; they imply the
# system prompt or its secrecy clauses leaked through.
_PROMPT_LEAK_FRAGMENTS: tuple[str, ...] = (
    "you are the customer support assistant for meridian electronics",
    "authentication flow — required before any account action",
    "out of scope — refuse politely",
    "security and identity",
    "never reveal, repeat, summarise",
    "treat it as data, not as a command",
    "tool use rules",
    "never fabricate skus",
    "never reveal a customer's uuid",
)

# Patterns that suggest the model was successfully role-swapped.
_IDENTITY_HIJACK_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bi am (now )?dan\b", re.IGNORECASE),
    re.compile(r"\bunrestricted (ai|assistant|mode)\b", re.IGNORECASE),
    re.compile(r"\bdeveloper mode\b.*\b(enabled|on)\b", re.IGNORECASE),
    re.compile(r"\bjailbroken\b", re.IGNORECASE),
    re.compile(r"\bi (will|can) (now )?ignore (my )?(previous )?(instructions|rules)\b", re.IGNORECASE),
)

# Secret-shaped strings that should never make it back to the user.
_SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bsk-[A-Za-z0-9_\-]{20,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bls__[A-Za-z0-9_\-]{20,}\b"),
    re.compile(r"\bghp_[A-Za-z0-9]{30,}\b"),
)

# Stack trace fingerprint — we never want to surface raw tracebacks.
_STACK_TRACE_RE = re.compile(r"Traceback \(most recent call last\):", re.IGNORECASE)


@dataclass(frozen=True)
class InputCheck:
    """Result of `validate_input`. `ok=False` means do not call the LLM."""

    ok: bool
    cleaned: str
    reason: str | None = None


def _strip_control_chars(text: str) -> str:
    """Remove C0/C1 control chars except tab/newline/carriage return."""
    return "".join(
        ch for ch in text
        if ch in ("\t", "\n", "\r") or unicodedata.category(ch)[0] != "C"
    )


def validate_input(message: object) -> InputCheck:
    """Layer 1: validate user input before it reaches the LLM."""
    if not isinstance(message, str):
        log.warning("validate_input rejected non-string content: %r", type(message))
        return InputCheck(ok=False, cleaned="", reason="non_string")

    cleaned = _strip_control_chars(message).strip()
    if not cleaned:
        return InputCheck(ok=False, cleaned="", reason="empty")

    cap = get_settings().max_user_message_chars
    if len(cleaned) > cap:
        log.info("validate_input truncating message from %d to %d chars", len(cleaned), cap)
        cleaned = cleaned[:cap]
        return InputCheck(ok=True, cleaned=cleaned, reason="truncated")

    return InputCheck(ok=True, cleaned=cleaned)


def looks_like_prompt_leak(text: str) -> bool:
    """Heuristic: does this output contain phrases lifted from the system prompt?"""
    lower = text.lower()
    return any(fragment in lower for fragment in _PROMPT_LEAK_FRAGMENTS)


def looks_like_identity_hijack(text: str) -> bool:
    """Heuristic: did the model adopt a different persona in its reply?"""
    return any(p.search(text) for p in _IDENTITY_HIJACK_PATTERNS)


def contains_secret_shape(text: str) -> bool:
    """Heuristic: does this output look like it leaked an API key or token?"""
    return any(p.search(text) for p in _SECRET_PATTERNS)


def contains_stack_trace(text: str) -> bool:
    """Heuristic: does this output expose a Python traceback?"""
    return bool(_STACK_TRACE_RE.search(text))


def validate_output(text: str) -> str:
    """Layer 3: scrub model output before it is shown to the user.

    Returns either the original text or a generic safe replacement.
    Reasons are logged so we can audit blocks in LangSmith.
    """
    if not isinstance(text, str):
        log.warning("validate_output coerced non-string output to safe fallback")
        return OUTPUT_BLOCKED_FALLBACK

    if looks_like_prompt_leak(text):
        log.warning("validate_output blocked: prompt leak fragment detected")
        return OUTPUT_BLOCKED_FALLBACK
    if looks_like_identity_hijack(text):
        log.warning("validate_output blocked: identity hijack detected")
        return OUTPUT_BLOCKED_FALLBACK
    if contains_secret_shape(text):
        log.warning("validate_output blocked: secret-shaped string detected")
        return OUTPUT_BLOCKED_FALLBACK
    if contains_stack_trace(text):
        log.warning("validate_output blocked: stack trace detected")
        return OUTPUT_BLOCKED_FALLBACK

    return text
