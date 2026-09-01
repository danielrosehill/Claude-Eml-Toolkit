---
name: redact-thread
description: Mask emails, phone numbers, national ID numbers, bank accounts, cards and IBANs in an email thread before it goes to a third party, then render the redacted PDF. Triggers on "redact this email thread", "remove personal details before I send this", "anonymise these emails".
---

# Redact a thread before sharing it

```bash
cd ${CLAUDE_PLUGIN_ROOT} && source .venv/bin/activate
PYTHONPATH=scripts python3 -m eml_toolkit.cli pdf <source> --out redacted.pdf \
  --redact --keep daniel@danielrosehill.co.il,REF-2026-0901
```

`--redact` alone applies the default rule set: `email`, `israeli_id`,
`phone_il`, `account`, `card`, `iban`. Narrow it with a comma-separated list,
e.g. `--redact email,card`. Available rules are in
`scripts/eml_toolkit/redact.py`.

`--keep` takes literal strings that are never masked — your own address, and the
reference number the recipient needs in order to act on the thread. Without it a
redacted complaint often becomes unactionable.

## How it redacts

Masking happens in the parsed JSON **before** the PDF is generated, so the
original values are not in the output file at all. The module also offers a
`blackout` concept for the case where a form demands visible black bars; that
leaves the text recoverable in the PDF content stream, which is why it is not
what `--redact` does.

The CLI prints a per-rule hit count to stderr. Report it. Then **read the
rendered PDF and check it yourself** — the patterns are deliberately
conservative, and the failure mode that matters is the one they missed, not the
one they over-masked. Israeli ID and generic account patterns in particular will
not catch a number written in words or split across a line break.
