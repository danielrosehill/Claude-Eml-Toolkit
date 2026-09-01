"""Direction resolution tests. These encode the cases that actually broke."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from bs4 import BeautifulSoup  # noqa: E402

from eml_toolkit import bidi  # noqa: E402


def test_hebrew_is_rtl():
    assert bidi.resolve_direction("שלום דניאל") == "rtl"


def test_english_is_ltr():
    assert bidi.resolve_direction("Hello Daniel") == "ltr"


def test_digits_alone_are_neutral_and_inherit_default():
    # An account number on its own line must not force LTR inside a Hebrew message.
    assert bidi.resolve_direction("123-456789", default="rtl") == "rtl"
    assert bidi.resolve_direction("123-456789", default="ltr") == "ltr"


def test_hebrew_majority_opening_with_latin_is_rtl():
    # The ratio override: first strong char is Latin, body is Hebrew.
    assert bidi.resolve_direction("REF-2026: שלום דניאל, מספר החשבון שלך הועבר") == "rtl"


def test_english_with_one_hebrew_word_stays_ltr():
    t = "Please see the attached document regarding the נספח and confirm receipt."
    assert bidi.resolve_direction(t) == "ltr"


def test_mixed_document_gets_per_paragraph_direction():
    html = ('<div><p>שלום דניאל, מספר החשבון 123-456789.</p>'
            '<p>Reference: REF-2026-0901</p></div>')
    soup = BeautifulSoup(html, "html.parser")
    doc_dir = bidi.annotate_html(soup)
    ps = soup.find_all("p")
    assert ps[0]["dir"] == "rtl"
    assert ps[1]["dir"] == "ltr"
    assert doc_dir == "rtl"


def test_nested_block_does_not_pollute_parent():
    # A Hebrew div wrapping a long English blockquote must stay RTL.
    html = ("<div><p>אני מבקש הסבר בכתב.</p>"
            "<blockquote><p>This is a long English quotation that would otherwise "
            "outvote the Hebrew above it by sheer character count.</p></blockquote></div>")
    soup = BeautifulSoup(html, "html.parser")
    bidi.annotate_html(soup)
    assert soup.find("p")["dir"] == "rtl"
    assert soup.find("blockquote").find("p")["dir"] == "ltr"


def test_sender_dir_is_respected():
    soup = BeautifulSoup('<p dir="ltr">שלום דניאל</p>', "html.parser")
    bidi.annotate_html(soup)
    assert soup.find("p")["dir"] == "ltr"


def test_plaintext_paragraphs_resolve_independently():
    text = "שלום דניאל,\n\nPlease find the details below.\n\nבברכה"
    out = bidi.wrap_plaintext(text)
    assert [d for d, _ in out] == ["rtl", "ltr", "rtl"]
