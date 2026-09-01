"""Per-block text direction resolution.

WeasyPrint (tested against 68.1 and 69.0) does not implement
``unicode-bidi: plaintext``; it emits::

    WARNING: Ignored `unicode-bidi:plaintext`, property not supported yet.

so a stylesheet cannot auto-resolve direction per paragraph. Direction has to be
decided here, at build time, and written onto each block element as an explicit
``dir`` attribute. See docs/bidi-constraint.md.

The rule implemented is the Unicode first-strong-character heuristic (UAX #9 P2/P3,
the same rule ``dir="auto"`` uses in browsers), with a ratio-based override for the
common email case of an RTL message carrying a long LTR quotation or signature.
"""

from __future__ import annotations

import unicodedata

# Strong RTL ranges: Hebrew, Arabic, Syriac, Thaana, NKo, Samaritan,
# Arabic Supplement/Extended-A, Hebrew+Arabic presentation forms.
_RTL_RANGES = (
    (0x0590, 0x05FF),
    (0x0600, 0x06FF),
    (0x0700, 0x074F),
    (0x0750, 0x077F),
    (0x0780, 0x07BF),
    (0x07C0, 0x07FF),
    (0x0800, 0x083F),
    (0x08A0, 0x08FF),
    (0xFB1D, 0xFDFF),
    (0xFE70, 0xFEFF),
)

# Characters that carry no direction of their own and must not cast a vote:
# formatting marks, and the isolate/embedding controls.
_NEUTRAL_CONTROLS = {
    0x200E, 0x200F,  # LRM, RLM  (these *are* strong, handled explicitly below)
    0x202A, 0x202B, 0x202C, 0x202D, 0x202E,
    0x2066, 0x2067, 0x2068, 0x2069,
}

LTR = "ltr"
RTL = "rtl"

#: Fraction of strong characters that must be RTL before a block whose first
#: strong character is LTR is nonetheless treated as RTL. Tuned for email:
#: an RTL message that opens with a Latin name or "Re:" is common.
RATIO_THRESHOLD = 0.40


def _is_rtl_char(cp: int) -> bool:
    return any(lo <= cp <= hi for lo, hi in _RTL_RANGES)


def _is_ltr_char(ch: str) -> bool:
    # Bidi class L covers Latin, Greek, Cyrillic, CJK and most else.
    return unicodedata.bidirectional(ch) == "L"


def strong_counts(text: str) -> tuple[int, int]:
    """Return ``(ltr_count, rtl_count)`` of strong directional characters."""
    ltr = rtl = 0
    for ch in text:
        cp = ord(ch)
        if cp == 0x200F:  # RLM is strong RTL
            rtl += 1
            continue
        if cp == 0x200E:  # LRM is strong LTR
            ltr += 1
            continue
        if cp in _NEUTRAL_CONTROLS:
            continue
        if _is_rtl_char(cp) and unicodedata.bidirectional(ch) in ("R", "AL"):
            rtl += 1
        elif _is_ltr_char(ch):
            ltr += 1
    return ltr, rtl


def resolve_direction(text: str, default: str = LTR) -> str:
    """Resolve the base direction for a single run of text.

    Digits and punctuation never vote: ``"123-456789"`` alone is directionally
    neutral and inherits ``default`` rather than forcing LTR. This matters
    because account and reference numbers are frequently the only content of a
    line in the kind of correspondence this plugin exists to render.
    """
    if not text or not text.strip():
        return default

    first_strong = None
    for ch in text:
        cp = ord(ch)
        if cp in _NEUTRAL_CONTROLS and cp not in (0x200E, 0x200F):
            continue
        if cp == 0x200F or (_is_rtl_char(cp) and unicodedata.bidirectional(ch) in ("R", "AL")):
            first_strong = RTL
            break
        if cp == 0x200E or _is_ltr_char(ch):
            first_strong = LTR
            break

    if first_strong is None:
        return default

    ltr, rtl = strong_counts(text)
    total = ltr + rtl
    if total and first_strong == LTR:
        # An RTL-majority block that merely opens with a Latin token is RTL.
        if rtl / total >= RATIO_THRESHOLD:
            return RTL
    return first_strong


#: Block-level elements that establish their own paragraph direction.
BLOCK_TAGS = {
    "p", "div", "li", "td", "th", "h1", "h2", "h3", "h4", "h5", "h6",
    "blockquote", "pre", "dd", "dt", "caption", "figcaption", "address",
}


def _own_text(el) -> str:
    """Text belonging to this block but not to any nested block.

    Without this a wrapping ``<div>`` would vote using every descendant's text,
    so a Hebrew message containing one long quoted English paragraph would set
    the whole container LTR and reverse the Hebrew above it.
    """
    parts = []
    for node in el.find_all(string=True):
        ancestor = node.parent
        nearest = None
        while ancestor is not None:
            if getattr(ancestor, "name", None) in BLOCK_TAGS:
                nearest = ancestor
                break
            ancestor = ancestor.parent
        if nearest is el:
            parts.append(str(node))
    return "".join(parts)


def annotate_html(soup, default: str = LTR) -> str:
    """Walk a BeautifulSoup tree and set ``dir`` on every text-bearing block.

    Returns the direction resolved for the document as a whole, which the caller
    should put on the wrapper element so that neutral blocks (a lone image, a
    horizontal rule) align with the bulk of the message.

    Blocks that already carry an explicit ``dir`` from the original message are
    left alone — the sender's own markup outranks our heuristic.
    """
    for el in soup.find_all(BLOCK_TAGS):
        if el.has_attr("dir"):
            continue
        own = _own_text(el)
        if not own.strip():
            continue
        el["dir"] = resolve_direction(own, default=default)

    whole = soup.get_text(" ", strip=True)
    return resolve_direction(whole, default=default)


def wrap_plaintext(text: str, default: str = LTR):
    """Split a plain-text body into per-paragraph ``(direction, text)`` pairs.

    Plain-text email is the harder case: there is no markup to hang ``dir`` on,
    and a Hebrew message quoting an English one is a single string. Splitting on
    blank lines and resolving each paragraph independently is what keeps the
    quoted English block from being reversed.
    """
    paragraphs = []
    for para in text.replace("\r\n", "\n").split("\n\n"):
        if not para.strip():
            continue
        paragraphs.append((resolve_direction(para, default=default), para))
    return paragraphs
