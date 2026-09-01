"""Render a parsed thread to a single paginated PDF via WeasyPrint.

Why not just call ``eml2pdf``: that package (which this one deliberately does not
duplicate) renders one message per PDF and writes no ``dir`` attributes at all —
verified 2026-09-01 by grepping its source for ``dir=|direction|rtl|bidi|lang=``,
which returns nothing. For a Hebrew thread that produces LTR paragraph direction
throughout, which detaches punctuation and breaks ``Name <addr@host>`` header
runs. We assemble our own HTML so that bidi.annotate_html can set direction per
block before WeasyPrint ever sees it.
"""

from __future__ import annotations

import html as html_lib
from datetime import datetime
from pathlib import Path

from bs4 import BeautifulSoup, Comment

from . import bidi

_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"

# Stripped before rendering: script/style never contribute to a printed record,
# and remote resources would phone home to the sender when the PDF is built.
_STRIP_TAGS = {"script", "style", "meta", "link", "base", "iframe", "object", "embed"}


def _sanitize(raw_html: str, embed_remote: bool = False) -> BeautifulSoup:
    soup = BeautifulSoup(raw_html or "", "html.parser")
    for tag in soup.find_all(_STRIP_TAGS):
        tag.decompose()
    for c in soup.find_all(string=lambda t: isinstance(t, Comment)):
        c.extract()
    if not embed_remote:
        # Tracking pixels and remote images: drop the src, keep a placeholder so
        # the reader can see that something was there.
        for img in soup.find_all("img"):
            src = (img.get("src") or "").strip().lower()
            if src.startswith(("http://", "https://")):
                img.replace_with(soup.new_string("[remote image not loaded]"))
    for tag in soup.find_all(True):
        for attr in list(tag.attrs):
            if attr.lower().startswith("on"):
                del tag[attr]
    return soup


# First-Strong Isolate / Pop Directional Isolate. Used instead of `<bdi>` or
# `unicode-bidi: isolate` because these are plain characters honoured by Pango's
# bidi pass, so they do not depend on WeasyPrint implementing the CSS property —
# which, for `plaintext`, it does not. Without the isolate the `<` of a
# `Name <addr>` pair detaches from the address whenever the display name is
# Hebrew, because the bracket is a neutral between an RTL run and an LTR one.
FSI = "\u2068"
PDI = "\u2069"


def _isolate(s: str) -> str:
    return f"{FSI}{s}{PDI}"


def _fmt_addr(a: dict) -> str:
    name, addr = a.get("name", ""), a.get("email", "")
    if name and addr:
        return (
            _isolate(html_lib.escape(name))
            + " "
            + _isolate(f"&lt;{html_lib.escape(addr)}&gt;")
        )
    return _isolate(html_lib.escape(addr or name))


def _fmt_addrs(addrs: list[dict]) -> str:
    return ", ".join(_fmt_addr(a) for a in addrs) if addrs else ""


def _fmt_date(iso: str | None) -> str:
    if not iso:
        return "(no date)"
    try:
        return datetime.fromisoformat(iso).strftime("%Y-%m-%d %H:%M %Z").strip()
    except ValueError:
        return iso


def message_body_html(msg: dict, collapse_quotes: bool = True) -> tuple[str, str]:
    """Return ``(direction, html)`` for one message body."""
    if msg.get("body_html"):
        soup = _sanitize(msg["body_html"])
        if collapse_quotes:
            for bq in soup.find_all("blockquote"):
                bq["class"] = bq.get("class", []) + ["quoted"]
        direction = bidi.annotate_html(soup)
        return direction, str(soup)

    text = msg.get("body_text") or ""
    paras = bidi.wrap_plaintext(text)
    parts = []
    for d, p in paras:
        quoted = " quoted" if p.lstrip().startswith(">") else ""
        parts.append(
            f'<p dir="{d}" class="pt{quoted}">{html_lib.escape(p)}</p>'
        )
    whole = bidi.resolve_direction(text)
    return whole, "\n".join(parts)


def render_thread_html(thread: dict, title: str | None = None,
                       collapse_quotes: bool = True) -> str:
    css = (_TEMPLATE_DIR / "thread.css").read_text(encoding="utf-8")
    subject = title or thread.get("subject") or "(no subject)"
    subj_dir = bidi.resolve_direction(subject)

    blocks = []
    for i, m in enumerate(thread["messages"], 1):
        body_dir, body = message_body_html(m, collapse_quotes=collapse_quotes)
        atts = ""
        if m.get("attachments"):
            items = "".join(
                f"<li>{html_lib.escape(a['filename'])} "
                f"<span class='meta'>({a['content_type']}, {a['size']:,} bytes, "
                f"sha256 {a['sha256'][:12]}…)</span></li>"
                for a in m["attachments"]
            )
            atts = f'<div class="attachments" dir="ltr"><h4>Attachments</h4><ul>{items}</ul></div>'

        hdr_rows = [("From", _fmt_addr(m["from"])), ("To", _fmt_addrs(m["to"]))]
        if m.get("cc"):
            hdr_rows.append(("Cc", _fmt_addrs(m["cc"])))
        hdr_rows.append(("Date", html_lib.escape(_fmt_date(m.get("date")))))
        msubj = m.get("subject", "")
        hdr_rows.append((
            "Subject",
            f'<span dir="{bidi.resolve_direction(msubj)}">{html_lib.escape(msubj)}</span>',
        ))
        rows = "".join(
            f"<tr><th>{k}</th><td>{v}</td></tr>" for k, v in hdr_rows
        )

        blocks.append(f"""
<section class="message" id="msg-{i}">
  <div class="msgnum">Message {i} of {len(thread['messages'])}</div>
  <table class="headers" dir="ltr">{rows}</table>
  <div class="body" dir="{body_dir}">{body}</div>
  {atts}
</section>""")

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>{html_lib.escape(subject)}</title>
<style>{css}</style></head>
<body>
<header class="cover">
  <h1 dir="{subj_dir}">{html_lib.escape(subject)}</h1>
  <p class="summary" dir="ltr">
    {thread['message_count']} message(s) &middot;
    {html_lib.escape(_fmt_date(thread.get('first_date')))} &rarr;
    {html_lib.escape(_fmt_date(thread.get('last_date')))}
  </p>
  <p class="participants" dir="ltr">{html_lib.escape(', '.join(thread.get('participants', [])))}</p>
</header>
{''.join(blocks)}
</body></html>"""


def render_thread_pdf(thread: dict, out_path: str | Path, **kwargs) -> Path:
    from weasyprint import HTML

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc = render_thread_html(thread, **kwargs)
    HTML(string=doc, base_url=str(_TEMPLATE_DIR)).write_pdf(str(out_path))
    return out_path
