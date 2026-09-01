import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from eml_toolkit import redact as RD  # noqa: E402


def test_email_is_masked_but_domain_kept():
    out, counts = RD.redact_text("write to daniel@example.com now", ("email",))
    assert "daniel@example.com" not in out
    assert "@example.com" in out
    assert counts["email"] == 1


def test_keep_list_exempts_a_literal():
    out, _ = RD.redact_text("daniel@example.com", ("email",), keep={"daniel@example.com"})
    assert out == "daniel@example.com"


def test_card_number_keeps_last_four():
    out, _ = RD.redact_text("4111 1111 1111 1111", ("card",))
    assert out.endswith("1111")
    assert "4111" not in out


def test_israeli_id_is_masked():
    out, counts = RD.redact_text("ת.ז. 123456789", ("israeli_id",))
    assert "123456789" not in out
    assert counts["israeli_id"] == 1


def test_redaction_happens_before_render_not_after():
    # Guards the design decision: the masked value must be gone from the data,
    # not merely painted over downstream.
    msg = {"subject": "acct 12-345678", "body_text": "call 054-1234567",
           "body_html": None, "from": {"name": "x", "email": "a@b.com"},
           "to": [], "cc": [], "bcc": []}
    out, counts = RD.redact_message(msg)
    assert "054-1234567" not in out["body_text"]
    assert "a@b.com" not in out["from"]["email"]
    assert counts


def test_thread_participants_are_rebuilt_after_redaction():
    # The cover page prints thread["participants"]; if it is not recomputed the
    # redacted PDF leaks every address on its first page.
    thread = {
        "subject": "s", "message_count": 1,
        "participants": ["leak@example.com"],
        "messages": [{
            "subject": "s", "body_text": "", "body_html": None,
            "from": {"name": "", "email": "leak@example.com"},
            "to": [], "cc": [], "bcc": [],
        }],
    }
    out, _ = RD.redact_thread(thread)
    assert "leak@example.com" not in out["participants"]
