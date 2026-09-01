# Claude-Eml-Toolkit

Claude Code plugin for turning `.eml` email exports into artefacts you can
actually use — a threaded PDF of a correspondence chain, extracted attachments,
Markdown for another agent, a redacted copy for a third party, or a numbered
evidence bundle for a complaint.

Built because nothing else reconstructs a **thread** and nothing else handles
**right-to-left** text. See [`docs/prior-art.md`](docs/prior-art.md).

## Skills

| Skill | Does |
| --- | --- |
| `parse-thread` | `.eml` / directory / `.mbox` → normalised thread JSON. Run first; everything else consumes it. |
| `thread-to-pdf` | The chain as one paginated PDF, with per-block bidi resolution. |
| `extract-attachments` | Attachments to disk, deduplicated by SHA-256, with a manifest. |
| `thread-to-markdown` | Structured Markdown for agents and repos. |
| `redact-thread` | Mask addresses, IDs, accounts, cards, IBANs, then render. |
| `bundle-evidence` | Exhibit bundle with per-source hashes. |

## Right-to-left

Hebrew and Arabic threads render correctly, and mixed threads render correctly
per paragraph — an English reply quoting Hebrew keeps both directions right.

There is deliberately **no separate RTL mode**. Real correspondence is mixed, so
a per-document switch gets the interesting cases wrong. Direction is resolved
per block from the text itself.

The mechanism, and the WeasyPrint limitation that forces it, are in
[`docs/bidi-constraint.md`](docs/bidi-constraint.md). Read that before changing
direction behaviour — in particular, **`pdftotext` is not a valid way to check
it** and will show a correct render as broken.

## Setup

```bash
cd "$(dirname "$0")"
uv venv .venv
source .venv/bin/activate
uv pip install weasyprint beautifulsoup4
```

Hebrew needs a Hebrew-capable font installed; the stylesheet asks for
`IBM Plex Sans Hebrew` then `DejaVu Sans`. Missing fonts render as boxes rather
than erroring.

## CLI

The skills wrap this; it is also usable directly.

```bash
PYTHONPATH=scripts python3 -m eml_toolkit.cli parse       <src> --out thread.json
PYTHONPATH=scripts python3 -m eml_toolkit.cli pdf         <src> --out chain.pdf [--redact] [--keep a,b]
PYTHONPATH=scripts python3 -m eml_toolkit.cli html        <src> --out chain.html
PYTHONPATH=scripts python3 -m eml_toolkit.cli markdown    <src> --out thread.md
PYTHONPATH=scripts python3 -m eml_toolkit.cli attachments <src> --out ./attachments
```

Every subcommand emits JSON on stdout so a skill can consume the result without
parsing prose.

## Status

v0.1.0. Threading, rendering, bidi, redaction and attachment extraction are
implemented and tested against the fixtures in `tests/`. `bundle-evidence` is
currently a documented procedure over the other commands rather than a single
subcommand.
