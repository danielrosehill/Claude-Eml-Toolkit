# Prior art, and why this repo exists anyway

Scanned 2026-09-01. Recording it so the "has someone already built this?"
question does not get re-asked from zero.

## Claude Code plugins / skills

**None.** Searched: the two personal marketplaces (`danielrosehill`,
`danielrosehill-private`, ~137 plugins), the official
`anthropics/claude-plugins-official` marketplace, the OpenViking skill substrate,
and GitHub code search for `eml path:**/SKILL.md`. No hits.

The nearest neighbours in the personal marketplaces, and why none of them cover
this:

| Plugin | Relationship |
| --- | --- |
| `spamhole` | The only other `.eml` consumer. Reads `inputs/emails/` for spam scoring, not document production. |
| `rtl-email` | RTL *composition and sending* (dir=rtl HTML into Gmail/Resend). Adjacent knowledge, opposite direction of travel. |
| `document-to-markdown` | PDF → Markdown. Opposite direction. |
| `digital-evidence` | Hashing, OpenTimestamps, BagIt. Complements `bundle-evidence`; does not parse mail. |
| `digital-printing`, `programmatic-doc-generation` | Downstream PDF handling, no email awareness. |

## Standalone tools

Several exist and are worth knowing about:

| Tool | Language | Notes |
| --- | --- | --- |
| [`eml2pdf`](https://github.com/klokie/eml-to-pdf) (fork of `plenaerts/eml2pdf`) | Python, on PyPI | The best of them. WeasyPrint-based, sanitises HTML, header block, attachment list with md5. Active as of Aug 2026. |
| `eledroos/EML-to-PDF` | Python | GUI-oriented batch converter, reportlab + optional weasyprint. |
| `aimaard/eml_to_pdf` | Ruby | |
| `BramEsposito/eml-to-pdf` | JavaScript | |

`eml2pdf` independently chose WeasyPrint, which is a good sign for that choice.

## What none of them do

Tested `eml2pdf` 2026-09-01 on a mixed Hebrew/English message:

- **No bidi handling at all.** `grep -rn 'dir=|direction|rtl|bidi|lang=' ` over
  its source returns nothing. Hebrew glyphs render, but with LTR paragraph
  direction, so `Name <addr>` header runs break and punctuation detaches. See
  [`bidi-constraint.md`](bidi-constraint.md).
- **One message per PDF.** `convert_dir` batches files into separate PDFs; there
  is no thread reconstruction, so a 12-message chain becomes 12 documents in
  arbitrary order.
- No redaction, no evidence manifest, no Markdown export.

Those four gaps are this repo's entire reason to exist. The single-message
rendering problem is genuinely solved by `eml2pdf`; had bidi and threading also
been solved, wrapping it would have been the right call instead.
