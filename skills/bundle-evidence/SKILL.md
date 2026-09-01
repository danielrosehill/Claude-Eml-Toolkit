---
name: bundle-evidence
description: Build a numbered exhibit bundle from an email export — cover page, index, continuous pagination, and a SHA-256 of every source .eml — for a complaint, a regulator, an insurer or a lawyer. Triggers on "make an evidence bundle", "exhibit bundle from these emails", "prepare these emails for a complaint".
---

# Build an evidence bundle

Produces a chain PDF plus an integrity manifest, so a recipient can verify that
the rendered correspondence matches the source files.

```bash
cd ${CLAUDE_PLUGIN_ROOT} && source .venv/bin/activate
PYTHONPATH=scripts python3 -m eml_toolkit.cli parse <source> --out bundle/thread.json
PYTHONPATH=scripts python3 -m eml_toolkit.cli pdf bundle/thread.json --out bundle/exhibit.pdf
PYTHONPATH=scripts python3 -m eml_toolkit.cli attachments <source> \
  --out bundle/attachments --manifest bundle/attachments/manifest.json
```

Then assemble `bundle/MANIFEST.md` yourself with: the source directory, the
count of messages, the date span, each source file with its SHA-256 (already in
`thread.json`), and the absolute date the bundle was produced.

## Rules for this skill

- **Never redact silently.** If the user wants redaction, run `redact-thread`
  and say in the manifest that the bundle is redacted and under which rules. An
  unmarked redacted bundle misrepresents the record.
- Hash the **source** `.eml` bytes, not the rendered PDF. The PDF is a
  derivative; the `.eml` is the evidence.
- Keep the unredacted originals out of the bundle directory so they cannot be
  sent by accident.
- State plainly that these hashes establish that the bundle is internally
  consistent, not that the emails are authentic. Authenticity comes from the
  mail provider, not from this tool. If the user needs a stronger claim, the
  `digital-evidence` plugin covers OpenTimestamps.
