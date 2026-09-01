---
name: parse-thread
description: Parse .eml files, a directory of them, or an .mbox into normalised thread JSON — headers, participants, bodies, attachment manifest, and reconstructed reply chains. Use this first; every other eml-toolkit skill consumes its output. Triggers on "parse these emails", "what's in this .eml", "reconstruct this email thread", "read this mbox".
---

# Parse an email export into thread JSON

Foundation skill. Produces the JSON contract that `thread-to-pdf`,
`thread-to-markdown`, `redact-thread` and `bundle-evidence` all read.

## Run it

```bash
cd ${CLAUDE_PLUGIN_ROOT} && source .venv/bin/activate
PYTHONPATH=scripts python3 -m eml_toolkit.cli parse <source> --out thread.json
```

`<source>` is a single `.eml`, a directory searched recursively for `*.eml`, or
an `.mbox`/`.mbx`.

Add `--strip-bodies` when you only need to see the structure — it replaces
bodies with a boolean and a 400-char excerpt, which keeps a 200-message export
readable in context.

## What it does

- Decodes RFC 2047 headers, so Hebrew display names come out as text, not `=?UTF-8?B?…`.
- Extracts both `text/html` and `text/plain` alternatives; downstream renderers
  prefer HTML and fall back to text.
- SHA-256s each source file and each attachment payload.
- Groups messages into threads by `References`/`In-Reply-To`, then falls back to
  normalised subject for messages that carry neither. The subject normaliser
  strips `Re:`/`Fwd:`/`AW:`/`SV:` and the Hebrew `תגובה:`/`הועבר:` and Arabic `رد:`.
- Sorts each thread chronologically; messages with an unparseable `Date` sort
  last rather than being dropped.

Threads come back largest-first, so `--thread 0` in the other skills is usually
the one you want.

## Reading the result

Report to the user: how many threads, how many messages in each, the date span,
and the participant list. If one source file produced its own singleton thread,
say so — that usually means its headers were stripped by whatever exported it,
and the subject fallback did not match either.
