"""Redaction for threads that are going to a third party.

Two modes, and the difference matters:

``mask``   replaces the characters in the JSON before rendering. The original
           text is not in the output PDF at all. This is the only mode safe for
           anything leaving your control.
``blackout`` wraps the run in ``<span class="redacted">`` which paints it black.
           The text is still in the PDF's content stream and is recoverable with
           any text extractor. Provided because it is sometimes what a form
           requires, and refused by default.

Patterns are deliberately conservative — over-redaction is cheap to spot and fix,
under-redaction is not.
"""

from __future__ import annotations

import re

PATTERNS: dict[str, re.Pattern] = {
    # Email addresses.
    "email": re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"),
    # Israeli teudat zehut: 9 digits, often written with separators.
    "israeli_id": re.compile(r"\b\d{9}\b"),
    # Israeli phone: 0XX-XXXXXXX / +972…
    "phone_il": re.compile(r"(?:\+972[-\s]?|\b0)(?:[23489]|5\d|7\d)[-\s]?\d{3}[-\s]?\d{4}\b"),
    # North American / generic international.
    "phone_intl": re.compile(r"\+?\d{1,3}[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"),
    # Bank / account numbers: 6+ digits with separators.
    "account": re.compile(r"\b\d{2,4}[-\s]\d{3,9}(?:[-\s]\d{2,9})?\b"),
    # Payment cards (Luhn not checked; 13–19 digits grouped).
    "card": re.compile(r"\b(?:\d[ -]?){13,19}\b"),
    "iban": re.compile(r"\b[A-Z]{2}\d{2}(?:[ ]?[A-Z0-9]{4}){2,7}\b"),
}

#: Applied unless the caller narrows the set.
DEFAULT_RULES = ("email", "israeli_id", "phone_il", "account", "card", "iban")


def _mask(match: re.Match) -> str:
    s = match.group(0)
    if "@" in s:
        local, _, domain = s.partition("@")
        keep = local[:1] if local else ""
        return f"{keep}{'•' * max(len(local) - 1, 3)}@{domain}"
    digits = [c for c in s if c.isdigit()]
    if len(digits) > 4:
        return "•" * (len(digits) - 4) + "".join(digits[-4:])
    return "•" * len(s)


def redact_text(text: str, rules=DEFAULT_RULES, keep: set[str] | None = None) -> tuple[str, dict]:
    """Return ``(redacted_text, {rule: hit_count})``.

    ``keep`` is a set of literal strings never to redact — your own address, the
    reference number the recipient needs to act on.
    """
    counts: dict[str, int] = {}
    keep = keep or set()
    out = text
    for rule in rules:
        pat = PATTERNS[rule]

        def sub(m, _rule=rule):
            if m.group(0) in keep:
                return m.group(0)
            counts[_rule] = counts.get(_rule, 0) + 1
            return _mask(m)

        out = pat.sub(sub, out)
    return out, counts


def redact_message(msg: dict, rules=DEFAULT_RULES, keep=None) -> tuple[dict, dict]:
    """Redact a parsed message in place-of-copy. Headers are redacted too."""
    m = dict(msg)
    total: dict[str, int] = {}

    def bump(c):
        for k, v in c.items():
            total[k] = total.get(k, 0) + v

    for field in ("body_text", "body_html", "subject"):
        if m.get(field):
            m[field], c = redact_text(m[field], rules, keep)
            bump(c)

    if "email" in rules:
        for field in ("to", "cc", "bcc"):
            for a in m.get(field) or []:
                if a.get("email") and a["email"] not in (keep or set()):
                    a["email"], c = redact_text(a["email"], ("email",), keep)
                    bump(c)
        f = m.get("from") or {}
        if f.get("email") and f["email"] not in (keep or set()):
            f["email"], c = redact_text(f["email"], ("email",), keep)
            bump(c)

    return m, total


def redact_thread(thread: dict, rules=DEFAULT_RULES, keep=None) -> tuple[dict, dict]:
    t = dict(thread)
    total: dict[str, int] = {}
    msgs = []
    for m in thread["messages"]:
        rm, c = redact_message(m, rules, keep)
        msgs.append(rm)
        for k, v in c.items():
            total[k] = total.get(k, 0) + v
    t["messages"] = msgs

    # Thread-level aggregates are computed at parse time from the unredacted
    # messages, so they must be rebuilt here. The participant list is printed on
    # the PDF cover page: leaving the parse-time value in place leaks every
    # address the per-message redaction just masked.
    t["participants"] = sorted({
        a["email"]
        for m in msgs
        for a in [m.get("from") or {}, *(m.get("to") or []), *(m.get("cc") or [])]
        if a.get("email")
    })
    if msgs:
        t["subject"] = msgs[0].get("subject", "")

    t["redaction_report"] = total
    return t, total
