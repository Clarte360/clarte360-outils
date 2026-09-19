from pathlib import Path
from unittest.mock import patch

PAGES = Path("clarte360_pip/ui/pages.py").read_text(encoding="utf-8")


def test_h32_removes_browser_pdf_iframe():
    assert "data:application/pdf;base64" not in PAGES
    assert "<iframe" not in PAGES
    assert "st.image(image_bytes" in PAGES
    assert "pdf_pages_as_png(pdf_bytes, 3, 4)" in PAGES


def test_h32_keeps_report_before_feeling_flow():
    assert "_render_pip_report_preview_before_feeling()" in PAGES
    assert "J’ai consulté ma synthèse — donner mon ressenti" in PAGES
    assert "pages essentielles de votre rapport PIP" in PAGES


def test_h32_renders_pages_3_and_4_server_side():
    from clarte360_pip.pdf_preview import pdf_pages_as_png

    class Proc:
        returncode = 0
        stderr = ""
        stdout = ""

    def fake_run(cmd, **kwargs):
        prefix = Path(cmd[-1])
        (prefix.parent / f"{prefix.name}-3.png").write_bytes(b"PNG3")
        (prefix.parent / f"{prefix.name}-4.png").write_bytes(b"PNG4")
        return Proc()

    with patch("clarte360_pip.pdf_preview.subprocess.run", side_effect=fake_run) as run:
        pages = pdf_pages_as_png(b"%PDF-test", 3, 4)
    assert pages == [b"PNG3", b"PNG4"]
    cmd = run.call_args.args[0]
    assert cmd[:4] == ["pdftoppm", "-png", "-r", "120"]
    assert cmd[cmd.index("-f") + 1] == "3"
    assert cmd[cmd.index("-l") + 1] == "4"
