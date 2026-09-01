---
name: thread-to-markdown
description: Export an email thread as structured Markdown for feeding to another agent, pasting into a repo, or summarising. Keeps headers and message boundaries, drops formatting. Triggers on "summarise this email thread", "convert these emails to markdown", "give me the text of this chain".
---

# Export a thread as Markdown

```bash
cd ${CLAUDE_PLUGIN_ROOT} && source .venv/bin/activate
PYTHONPATH=scripts python3 -m eml_toolkit.cli markdown <source> --out thread.md
```

Use this rather than `thread-to-pdf` when the consumer is an agent or a repo.
PDF is for humans and for the record; Markdown is for work.

Each message keeps a header block including its `Message-ID`, so a later
reference to "message 3" is unambiguous. Quoted history collapses to a single
`> _[quoted history omitted]_` marker by default — the thread already contains
the quoted message in full further up, and leaving it in roughly doubles the
token cost of a long chain. Pass `--keep-quotes` when the quoting itself is what
you are examining, e.g. establishing what someone was actually replying to.

Attachments are listed with sizes and hashes but not extracted; use
`extract-attachments` for the payloads.
