"""Parse .eml / .mbox into normalised message dicts and reconstruct threads.

Output shape is stable and is the contract every other module in this package
consumes. One message::

    {
      "source_file": "inbox/001.eml",
      "sha256": "…",                       # of the raw .eml bytes
      "message_id": "<a1@example.com>",
      "in_reply_to": "<a0@example.com>",
      "references": ["<a0@example.com>"],
      "date": "2026-09-01T09:00:00+03:00",  # ISO 8601, None if unparseable
      "from": {"name": "…", "email": "…"},
      "to":   [{"name": "…", "email": "…"}],
      "cc":   [...], "bcc": [...],
      "subject": "…",
      "body_html": "…" or None,
      "body_text": "…" or None,
      "attachments": [
        {"filename": "…", "content_type": "…", "size": 1234,
         "sha256": "…", "content_id": "…", "inline": false}
      ]
    }
"""

from __future__ import annotations

import email
import email.policy
import hashlib
import mailbox
import re
from datetime import datetime
from email.header import decode_header, make_header
from email.utils import getaddresses, parsedate_to_datetime
from pathlib import Path

# "Re:", "Fwd:", "RE :", Hebrew "תגובה:", "הועבר:", Arabic "رد:" …
_SUBJECT_PREFIX = re.compile(
    r"^\s*(?:(?:re|fw|fwd|aw|sv|vs|תגובה|הועבר|رد|إعادة توجيه)\s*(?:\[\d+\])?\s*:\s*)+",
    re.IGNORECASE,
)


def _decode(value) -> str:
    if value is None:
        return ""
    try:
        return str(make_header(decode_header(str(value))))
    except Exception:
        return str(value)


def _addresses(msg, field) -> list[dict]:
    raw = msg.get_all(field, [])
    if not raw:
        return []
    out = []
    for name, addr in getaddresses([_decode(v) for v in raw]):
        if not name and not addr:
            continue
        out.append({"name": name.strip(), "email": addr.strip().lower()})
    return out


def _date(msg) -> str | None:
    raw = msg.get("Date")
    if not raw:
        return None
    try:
        dt = parsedate_to_datetime(raw)
    except Exception:
        return None
    if dt is None:
        return None
    return dt.isoformat()


def _bodies(msg) -> tuple[str | None, str | None]:
    """Return ``(html, text)``, preferring the richest part of each type."""
    html = text = None
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_maintype() == "multipart":
                continue
            disp = (part.get_content_disposition() or "").lower()
            if disp == "attachment":
                continue
            ctype = part.get_content_type()
            try:
                payload = part.get_content()
            except Exception:
                payload = part.get_payload(decode=True)
                if isinstance(payload, bytes):
                    charset = part.get_content_charset() or "utf-8"
                    payload = payload.decode(charset, errors="replace")
            if ctype == "text/html" and html is None:
                html = payload
            elif ctype == "text/plain" and text is None:
                text = payload
    else:
        try:
            payload = msg.get_content()
        except Exception:
            payload = msg.get_payload(decode=True)
            if isinstance(payload, bytes):
                payload = payload.decode(msg.get_content_charset() or "utf-8", errors="replace")
        if msg.get_content_type() == "text/html":
            html = payload
        else:
            text = payload
    return html, text


def _attachments(msg) -> list[dict]:
    out = []
    if not msg.is_multipart():
        return out
    for part in msg.walk():
        if part.get_content_maintype() == "multipart":
            continue
        disp = (part.get_content_disposition() or "").lower()
        cid = (part.get("Content-ID") or "").strip("<>") or None
        if disp != "attachment" and not (disp == "inline" and cid):
            continue
        data = part.get_payload(decode=True) or b""
        out.append({
            "filename": _decode(part.get_filename()) or f"unnamed-{len(out) + 1}",
            "content_type": part.get_content_type(),
            "size": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
            "content_id": cid,
            "inline": disp == "inline",
        })
    return out


def parse_bytes(raw: bytes, source: str = "<bytes>") -> dict:
    msg = email.message_from_bytes(raw, policy=email.policy.default)
    html, text = _bodies(msg)
    refs = (msg.get("References") or "").split()
    return {
        "source_file": source,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "message_id": (msg.get("Message-ID") or "").strip() or None,
        "in_reply_to": (msg.get("In-Reply-To") or "").strip() or None,
        "references": [r.strip() for r in refs if r.strip()],
        "date": _date(msg),
        "from": (_addresses(msg, "From") or [{"name": "", "email": ""}])[0],
        "to": _addresses(msg, "To"),
        "cc": _addresses(msg, "Cc"),
        "bcc": _addresses(msg, "Bcc"),
        "subject": _decode(msg.get("Subject")),
        "body_html": html,
        "body_text": text,
        "attachments": _attachments(msg),
    }


def parse_file(path: str | Path) -> dict:
    path = Path(path)
    return parse_bytes(path.read_bytes(), source=str(path))


def parse_source(path: str | Path) -> list[dict]:
    """Parse a single .eml, a directory of .eml files, or an .mbox."""
    path = Path(path)
    if path.is_dir():
        return [parse_file(p) for p in sorted(path.rglob("*.eml"))]
    if path.suffix.lower() in (".mbox", ".mbx"):
        box = mailbox.mbox(str(path))
        out = []
        for i, m in enumerate(box):
            out.append(parse_bytes(m.as_bytes(), source=f"{path}#{i}"))
        return out
    return [parse_file(path)]


def normalise_subject(subject: str) -> str:
    prev = None
    s = subject or ""
    while prev != s:
        prev = s
        s = _SUBJECT_PREFIX.sub("", s)
    return s.strip().lower()


def _sort_key(m: dict):
    # Messages without a parseable Date sort last but keep a stable order.
    if m.get("date"):
        try:
            return (0, datetime.fromisoformat(m["date"]).timestamp())
        except ValueError:
            pass
    return (1, m.get("source_file", ""))


def build_thread(messages: list[dict]) -> dict:
    """Group messages into threads and order each chronologically.

    Primary linkage is ``References`` / ``In-Reply-To`` (RFC 5322). Messages that
    carry no usable linkage — common in Outlook exports and in anything that has
    been through a print-to-eml step — fall back to normalised subject.

    Returns ``{"threads": [{"subject": …, "messages": [...]}, ...]}`` with the
    largest thread first.
    """
    by_id = {m["message_id"]: m for m in messages if m.get("message_id")}

    parent = {}

    def find(x):
        while parent.get(x, x) != x:
            parent[x] = parent.get(parent[x], parent[x])
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    keys = []
    for m in messages:
        k = m.get("message_id") or f"file:{m['source_file']}"
        m["_key"] = k
        parent.setdefault(k, k)
        keys.append(k)

    for m in messages:
        k = m["_key"]
        for ref in ([m["in_reply_to"]] if m.get("in_reply_to") else []) + m.get("references", []):
            if ref in by_id:
                union(by_id[ref]["_key"], k)

    # Subject fallback for anything still isolated.
    by_subject: dict[str, str] = {}
    for m in messages:
        if not m.get("in_reply_to") and not m.get("references"):
            subj = normalise_subject(m.get("subject", ""))
            if not subj:
                continue
            if subj in by_subject:
                union(by_subject[subj], m["_key"])
            else:
                by_subject[subj] = m["_key"]

    groups: dict[str, list[dict]] = {}
    for m in messages:
        groups.setdefault(find(m["_key"]), []).append(m)

    threads = []
    for msgs in groups.values():
        msgs.sort(key=_sort_key)
        for m in msgs:
            m.pop("_key", None)
        threads.append({
            "subject": msgs[0].get("subject", "") if msgs else "",
            "message_count": len(msgs),
            "participants": sorted({
                a["email"]
                for m in msgs
                for a in [m["from"], *m["to"], *m["cc"]]
                if a.get("email")
            }),
            "first_date": msgs[0].get("date") if msgs else None,
            "last_date": msgs[-1].get("date") if msgs else None,
            "messages": msgs,
        })

    threads.sort(key=lambda t: (-t["message_count"], t["first_date"] or ""))
    return {"threads": threads}
