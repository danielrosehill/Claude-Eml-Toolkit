---
name: thread-to-pdf
description: Render an email thread to a single paginated PDF with correct bidirectional text — Hebrew and Arabic messages come out right-to-left, English ones left-to-right, in the same document. Use for archiving correspondence, sending a chain to a lawyer or regulator, or producing a readable record from loose .eml files. Triggers on "PDF of this email chain", "print this thread", "make a PDF of these emails", "RTL email PDF", "Hebrew email to PDF".
---

# Render an email thread to PDF

## Run it

```bash
cd ${CLAUDE_PLUGIN_ROOT} && source .venv/bin/activate
PYTHONPATH=scripts python3 -m eml_toolkit.cli pdf <source> --out chain.pdf
```

`<source>` is anything `parse-thread` accepts, or a `thread.json` it produced.

| Flag | Use |
| --- | --- |
| `--thread N` | Pick a thread when the source held more than one (default 0, the largest) |
| `--title "…"` | Override the cover heading |
| `--keep-quotes` | Render quoted history at full weight instead of demoting it |
| `--redact` | Apply default redaction rules before rendering — see `redact-thread` |
| `--keep a,b` | Literals never to redact (your own address, a reference number) |

Use `... cli html <source> --out chain.html` to inspect the intermediate markup
when a render looks wrong. That is the fastest way to see what direction each
block was assigned.

## Direction is handled for you — do not add CSS for it

Do not try to fix an RTL problem by editing `scripts/templates/thread.css`.
WeasyPrint does not implement `unicode-bidi: plaintext`, so direction cannot be
resolved in CSS at all; it is decided per block in `scripts/eml_toolkit/bidi.py`
and written as an explicit `dir` attribute before WeasyPrint sees the document.
Full reasoning in `docs/bidi-constraint.md` — read it before touching direction
behaviour.

There is no separate "RTL mode", deliberately. Real threads are mixed: a Hebrew
body with an English signature, or an English reply quoting Hebrew. A per-thread
RTL switch gets exactly those cases wrong, so each block is resolved on its own.

## Verifying a render

`pdftotext` reports **logical** order with embedding marks, so it will show
`‫< מזרחי טפחות‬service@…>` for a header that is in fact rendering correctly.
It is not a valid oracle for direction. To check visually:

```bash
pdftoppm -png -r 100 -f 1 -l 1 chain.pdf /tmp/page && # then read /tmp/page-1.png
```

Read the PNG. Confirm Hebrew paragraphs are right-aligned, Latin ones are
left-aligned, and `Name <address>` pairs are intact.
