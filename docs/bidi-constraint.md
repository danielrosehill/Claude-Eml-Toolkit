# Bidirectional text in WeasyPrint-rendered email

Verified 2026-09-01 against WeasyPrint 68.1 (system) and 69.0 (in this repo's
`.venv`), Python 3.13, on Ubuntu. Read this before changing anything about text
direction.

## The constraint

**WeasyPrint does not implement `unicode-bidi: plaintext`.** It parses the
declaration, discards it, and warns:

```
WARNING: Ignored `unicode-bidi:plaintext` at 1:56, property not supported yet.
```

That rules out the obvious design — one stylesheet with
`unicode-bidi: plaintext` letting each paragraph resolve its own direction from
its first strong character. It silently does nothing, which is worse than
failing, because the output still renders and looks plausible until you check a
mixed-direction document.

Confirmed by direct test: an HTML document with `dir="rtl"` on `<html>` and
`unicode-bidi: plaintext` on paragraphs rendered an English paragraph with the
full stop relocated to the left — i.e. the LTR paragraph inherited RTL base
direction, exactly what `plaintext` exists to prevent.

## The consequence for this repo

Direction is resolved in Python, per block, at build time, and written as an
explicit `dir` attribute on each block element before WeasyPrint sees the
document. That is `scripts/eml_toolkit/bidi.py`, applied by
`render.message_body_html`.

`scripts/templates/thread.css` therefore contains **no direction logic** beyond
`text-align` rules keyed off the `dir` attribute the Python already set. Adding
`direction:` or `unicode-bidi:` declarations there will not work, and will look
like it might.

## What `bidi.py` implements

The Unicode first-strong-character heuristic (UAX #9, rules P2/P3 — the same
rule browsers use for `dir="auto"`), plus one deviation:

- **Ratio override.** A block whose first strong character is LTR but which is
  ≥40% strong-RTL is treated as RTL. Tuned for email, where a Hebrew message
  opening with a Latin sender name, a `Re:`, or a product name is routine and
  the first-strong rule alone gets it backwards.
- **Digits and punctuation never vote.** A line containing only
  `123-456789` is directionally neutral and inherits the surrounding default
  rather than forcing LTR. Account and reference numbers are frequently a whole
  line on their own in exactly the correspondence this tool renders.
- **`_own_text`.** A block votes using only the text it owns directly, not text
  inside nested blocks. Without this a wrapping `<div>` counts every
  descendant's characters, so a Hebrew message containing one long quoted
  English paragraph sets the container LTR and reverses the Hebrew above it.
- **Sender markup wins.** A block that already carries `dir` from the original
  message is left alone.

## The `Name <address>` defect, and the fix

An RTL display name followed by an LTR address detaches the angle bracket:

```
rendered:  ‹ מזרחי טפחות‹service@mizrahi.co.il>
wanted:    מזרחי טפחות <service@mizrahi.co.il>
```

The bracket is a *neutral* character sitting between an RTL run and an LTR run,
so UAX #9 resolves it to the paragraph direction, which detaches it from the
address it belongs to.

Fixed in `render._fmt_addr` by wrapping the name and the bracketed address in
**U+2068 FIRST STRONG ISOLATE** and **U+2069 POP DIRECTIONAL ISOLATE**.

Isolate *characters* rather than `<bdi>` or `unicode-bidi: isolate`, deliberately:
the characters are handled by Pango's bidi pass and do not depend on WeasyPrint
implementing any CSS property. Given that it does not implement `plaintext`,
assuming it implements `isolate` would be an unforced bet.

## Do not use `pdftotext` to verify direction

`pdftotext` emits **logical** order with the embedding marks left in. A header
that renders perfectly comes out looking broken:

```
$ pdftotext chain.pdf -
‫< מזרחי טפחות‬service@mizrahi.co.il>
```

That output is what a *correct* render looks like under `pdftotext`. Chasing it
as a bug wastes an afternoon — it did during development of this repo, after the
isolate fix had already landed and the extractor kept showing the old shape.

Verify visually instead:

```bash
pdftoppm -png -r 100 -f 1 -l 1 chain.pdf /tmp/page   # then look at /tmp/page-1.png
```

## Fonts

`IBM Plex Sans Hebrew` is first in the stack and covers Hebrew and Latin, so a
mixed thread keeps one typeface. `DejaVu Sans` follows and carries Arabic.
Both were present on the development machine; the CSS degrades to `sans-serif`
rather than failing if neither is installed, which produces tofu for Hebrew
rather than an error. If Hebrew renders as boxes, that is a missing font, not a
bidi problem.
