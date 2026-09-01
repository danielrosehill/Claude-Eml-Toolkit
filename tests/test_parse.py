import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from eml_toolkit import parse as P  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "thread"


def test_thread_is_reconstructed_in_order():
    result = P.build_thread(P.parse_source(FIXTURES))
    assert len(result["threads"]) == 1
    t = result["threads"][0]
    assert t["message_count"] == 5
    dates = [m["date"] for m in t["messages"]]
    assert dates == sorted(dates)


def test_hebrew_headers_are_decoded():
    t = P.build_thread(P.parse_source(FIXTURES))["threads"][0]
    assert t["messages"][0]["from"]["name"] == "מזרחי טפחות"
    assert "סגירת סניף" in t["messages"][0]["subject"]


def test_participants_deduplicated():
    t = P.build_thread(P.parse_source(FIXTURES))["threads"][0]
    assert t["participants"] == [
        "daniel@danielrosehill.co.il", "service@mizrahi.co.il"
    ]


def test_subject_normalisation_strips_prefixes():
    assert P.normalise_subject("Re: Fwd: תגובה: Hello") == "hello"
    assert P.normalise_subject("RE[2]: Hello") == "hello"


def test_source_files_are_hashed():
    msgs = P.parse_source(FIXTURES)
    assert all(len(m["sha256"]) == 64 for m in msgs)


def test_attachments_are_hashed_and_listed():
    t = P.build_thread(P.parse_source(FIXTURES))["threads"][0]
    atts = [a for m in t["messages"] for a in m["attachments"]]
    assert len(atts) == 2
    assert atts[0]["filename"] == "letter.pdf"
    # Same payload in both messages -> identical digest, which is what the
    # extractor deduplicates on.
    assert atts[0]["sha256"] == atts[1]["sha256"]


def test_all_five_messages_land_in_one_thread():
    # Messages 4 and 5 link via References to the head of the chain.
    assert len(P.build_thread(P.parse_source(FIXTURES))["threads"]) == 1
