"""Thread -> Markdown, for handing correspondence to another agent or repo.

Deliberately lossy in one direction only: formatting goes, structure stays.
Every message keeps its headers as a YAML-ish block so a reader can cite
"message 3" without ambiguity.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup


def _html_to_text(html: str) -> str:
    soup = BeautifulSoup(html or "", "html.parser")
    for t in soup.find_all(["script", "style"]):
        t.decompose()
    for br in soup.find_all("br"):
        br.replace_with("\n")
    for p in soup.find_all(["p", "div", "li", "tr"]):
        p.append(soup.new_string("\n"))
    text = soup.get_text()
    text = re.sub(r"[ \t]+\n", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _addr(a: dict) -> str:
    n, e = a.get("name", ""), a.get("email", "")
    return f"{n} <{e}>" if n and e else (e or n)


def thread_to_markdown(thread: dict, collapse_quotes: bool = True) -> str:
    lines = [
        f"# {thread.get('subject') or '(no subject)'}",
        "",
        f"- **Messages:** {thread['message_count']}",
        f"- **Span:** {thread.get('first_date')} → {thread.get('last_date')}",
        f"- **Participants:** {', '.join(thread.get('participants', []))}",
        "",
        "---",
        "",
    ]
    for i, m in enumerate(thread["messages"], 1):
        lines += [
            f"## Message {i}",
            "",
            f"- **From:** {_addr(m['from'])}",
            f"- **To:** {', '.join(_addr(a) for a in m['to'])}" if m.get("to") else "",
            f"- **Cc:** {', '.join(_addr(a) for a in m['cc'])}" if m.get("cc") else "",
            f"- **Date:** {m.get('date') or '(none)'}",
            f"- **Subject:** {m.get('subject', '')}",
            f"- **Message-ID:** `{m.get('message_id') or '(none)'}`",
            "",
        ]
        body = _html_to_text(m["body_html"]) if m.get("body_html") else (m.get("body_text") or "")
        if collapse_quotes:
            kept = []
            for para in body.split("\n\n"):
                if para.lstrip().startswith(">"):
                    kept.append("> _[quoted history omitted — see earlier messages]_")
                else:
                    kept.append(para)
            # collapse runs of consecutive omission markers
            body = re.sub(
                r"(> _\[quoted history omitted[^\]]*\]_\n\n)+",
                "> _[quoted history omitted — see earlier messages]_\n\n",
                "\n\n".join(kept),
            )
        lines += [body.strip(), ""]
        if m.get("attachments"):
            lines.append("**Attachments:**")
            lines += [
                f"- `{a['filename']}` — {a['content_type']}, {a['size']:,} bytes, "
                f"sha256 `{a['sha256'][:16]}…`"
                for a in m["attachments"]
            ]
            lines.append("")
        lines += ["---", ""]
    return "\n".join(l for l in lines if l != "")
