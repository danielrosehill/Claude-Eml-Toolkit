# Claude-Eml-Toolkit — working notes

## Before changing text direction behaviour

Read `docs/bidi-constraint.md` first. Two things there will otherwise cost you
an afternoon each:

1. WeasyPrint does not implement `unicode-bidi: plaintext`. Direction cannot be
   fixed in `scripts/templates/thread.css`; it is resolved in
   `scripts/eml_toolkit/bidi.py` and written as `dir` attributes at build time.
2. `pdftotext` prints logical order with embedding marks. A correct render looks
   broken under it. Verify with `pdftoppm -png` and look at the image.

## Layout

```
scripts/eml_toolkit/
  parse.py     .eml/.mbox -> normalised dicts; thread reconstruction
  bidi.py      per-block direction resolution   <- the novel part
  render.py    thread -> HTML -> PDF (WeasyPrint)
  redact.py    pattern masking, applied to JSON before render
  markdown.py  thread -> Markdown
  cli.py       argparse front end; every command emits JSON
scripts/templates/thread.css   print stylesheet, no direction logic
skills/        one directory per skill
tests/fixtures/thread/         5-message mixed Hebrew/English chain, 2 with a
                               duplicate attachment (exercises dedupe)
```

## Conventions

- The dict shape emitted by `parse.py` is the contract between modules. Changing
  it means changing every consumer; document it in the module docstring if you do.
- Redaction operates on the parsed JSON, never on the rendered PDF. Anything that
  only paints over text in the PDF leaves it recoverable.
- Hash source `.eml` bytes, not derivatives.

## Deliberately not done

- Not wrapping `eml2pdf`. It solves single-message rendering well but has no bidi
  and no threading, which is most of the value here. Reasoning in
  `docs/prior-art.md`.
- No remote image fetching during render — a tracking pixel would phone home to
  the sender at build time. Remote `<img>` is replaced with a placeholder.
