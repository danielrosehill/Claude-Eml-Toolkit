---
name: extract-attachments
description: Pull every attachment out of an .eml export to disk with a hash-deduped JSON manifest. Use when you need the files themselves rather than a rendering of the correspondence. Triggers on "get the attachments out of these emails", "extract email attachments", "what was attached to this thread".
---

# Extract attachments from an email export

```bash
cd ${CLAUDE_PLUGIN_ROOT} && source .venv/bin/activate
PYTHONPATH=scripts python3 -m eml_toolkit.cli attachments <source> \
  --out ./attachments --manifest ./attachments/manifest.json
```

## Behaviour worth knowing

- Deduplicates by SHA-256 of the payload, not by filename. The same PDF attached
  to five messages in a chain is written once; the other four appear in the
  manifest with `"written": false` and a `duplicate_of` path. This matters
  because quoting an email usually re-attaches its attachments.
- Filename collisions between *different* files get `-1`, `-2` suffixes rather
  than overwriting.
- Inline images with a `Content-ID` are extracted too — they are how signatures
  and embedded screenshots arrive, and a manifest that silently omitted them
  would misrepresent what was sent.
- Attachment filenames come from the message and are attacker-controlled. The
  CLI writes basenames into the output directory only.

Report the count written, the count deduplicated, and any file whose declared
`content_type` disagrees with its extension.
