"""CLI for eml-toolkit. Every subcommand emits JSON on stdout unless told
otherwise, so skills can consume the result without scraping prose."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from . import parse as P
from . import redact as RD
from . import render as R


def _emit(obj, out=None):
    text = json.dumps(obj, ensure_ascii=False, indent=2)
    if out:
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Path(out).write_text(text, encoding="utf-8")
    else:
        print(text)


def _load_thread(args) -> dict:
    """Accept either a source of .eml files or a previously written thread JSON."""
    src = Path(args.source)
    if src.suffix.lower() == ".json":
        data = json.loads(src.read_text(encoding="utf-8"))
        threads = data["threads"] if "threads" in data else [data]
    else:
        threads = P.build_thread(P.parse_source(src))["threads"]
    idx = getattr(args, "thread", 0)
    if idx >= len(threads):
        sys.exit(f"thread index {idx} out of range ({len(threads)} found)")
    return threads[idx]


def cmd_parse(args):
    msgs = P.parse_source(args.source)
    result = P.build_thread(msgs)
    if args.strip_bodies:
        for t in result["threads"]:
            for m in t["messages"]:
                m["body_html"] = bool(m.get("body_html"))
                m["body_text"] = (m.get("body_text") or "")[:400]
    _emit(result, args.out)


def cmd_pdf(args):
    thread = _load_thread(args)
    if args.redact:
        rules = args.redact.split(",") if args.redact != "default" else RD.DEFAULT_RULES
        keep = set(args.keep.split(",")) if args.keep else None
        thread, report = RD.redact_thread(thread, rules, keep)
        print(f"redacted: {report}", file=sys.stderr)
    out = R.render_thread_pdf(
        thread, args.out,
        title=args.title,
        collapse_quotes=not args.keep_quotes,
    )
    _emit({"pdf": str(out), "messages": thread["message_count"],
           "subject": thread["subject"]})


def cmd_html(args):
    thread = _load_thread(args)
    doc = R.render_thread_html(thread, title=args.title,
                               collapse_quotes=not args.keep_quotes)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(doc, encoding="utf-8")
    _emit({"html": args.out})


def cmd_attachments(args):
    msgs = P.parse_source(args.source)
    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)
    import email
    import email.policy

    manifest, seen = [], {}
    for m in msgs:
        if not m["attachments"]:
            continue
        src = m["source_file"].split("#")[0]
        raw = Path(src).read_bytes()
        parsed = email.message_from_bytes(raw, policy=email.policy.default)
        for part in parsed.walk():
            if part.get_content_maintype() == "multipart":
                continue
            disp = (part.get_content_disposition() or "").lower()
            cid = (part.get("Content-ID") or "").strip("<>") or None
            if disp != "attachment" and not (disp == "inline" and cid):
                continue
            data = part.get_payload(decode=True) or b""
            digest = hashlib.sha256(data).hexdigest()
            name = P._decode(part.get_filename()) or f"unnamed-{digest[:8]}"
            if digest in seen:
                manifest.append({"filename": name, "sha256": digest,
                                 "duplicate_of": seen[digest], "written": False})
                continue
            dest = outdir / name
            n = 1
            while dest.exists():
                dest = outdir / f"{Path(name).stem}-{n}{Path(name).suffix}"
                n += 1
            dest.write_bytes(data)
            seen[digest] = str(dest)
            manifest.append({"filename": name, "path": str(dest), "size": len(data),
                             "sha256": digest, "content_type": part.get_content_type(),
                             "from_message": m.get("message_id"), "written": True})
    _emit({"output_dir": str(outdir), "count": sum(1 for a in manifest if a["written"]),
           "duplicates": sum(1 for a in manifest if not a["written"]),
           "attachments": manifest}, args.manifest)


def cmd_markdown(args):
    thread = _load_thread(args)
    from .markdown import thread_to_markdown
    md = thread_to_markdown(thread, collapse_quotes=not args.keep_quotes)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(md, encoding="utf-8")
    _emit({"markdown": args.out, "messages": thread["message_count"]})


def main(argv=None):
    p = argparse.ArgumentParser(prog="eml-toolkit", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("parse", help="parse .eml/dir/.mbox into thread JSON")
    sp.add_argument("source")
    sp.add_argument("--out", help="write JSON here instead of stdout")
    sp.add_argument("--strip-bodies", action="store_true",
                    help="omit full bodies — for inspecting structure cheaply")
    sp.set_defaults(func=cmd_parse)

    for name, fn, needs_out in (("pdf", cmd_pdf, True), ("html", cmd_html, True)):
        s = sub.add_parser(name, help=f"render a thread to {name.upper()}")
        s.add_argument("source", help=".eml / directory / .mbox / thread JSON")
        s.add_argument("--out", required=needs_out)
        s.add_argument("--thread", type=int, default=0, help="thread index (default 0, the largest)")
        s.add_argument("--title")
        s.add_argument("--keep-quotes", action="store_true",
                       help="render quoted history at full weight")
        if name == "pdf":
            s.add_argument("--redact", nargs="?", const="default",
                           help="'default' or comma-separated rules: "
                                + ",".join(RD.PATTERNS))
            s.add_argument("--keep", help="comma-separated literals never to redact")
        s.set_defaults(func=fn)

    sa = sub.add_parser("attachments", help="extract attachments with a manifest")
    sa.add_argument("source")
    sa.add_argument("--out", required=True, help="output directory")
    sa.add_argument("--manifest", help="write the JSON manifest here too")
    sa.set_defaults(func=cmd_attachments)

    sm = sub.add_parser("markdown", help="export a thread as Markdown")
    sm.add_argument("source")
    sm.add_argument("--out", required=True)
    sm.add_argument("--thread", type=int, default=0)
    sm.add_argument("--keep-quotes", action="store_true")
    sm.set_defaults(func=cmd_markdown)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    main()
