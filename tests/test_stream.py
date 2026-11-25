import pytest

from pi_virtual_whiteboard.stream import web_file


def test_web_file_serves_the_page_at_the_root() -> None:
    file = web_file("/")
    assert file is not None
    assert file[1] == "text/html; charset=utf-8"


def test_web_file_serves_scripts_as_javascript() -> None:
    file = web_file("/app.js")
    assert file is not None
    assert file[1] == "text/javascript; charset=utf-8"


def test_web_file_serves_the_bundled_font() -> None:
    file = web_file("/fonts/anton.woff2")
    assert file is not None
    assert file[1] == "font/woff2"


@pytest.mark.parametrize("path", ["/fonts/OFL.txt", "/../config.py", "/../../pyproject.toml", "/missing.js", "/web"])
def test_web_file_serves_nothing_outside_the_page(path: str) -> None:
    assert web_file(path) is None
