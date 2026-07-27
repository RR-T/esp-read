"""Shared fixtures: a synthetic EPUB and a temp library, so the whole pipeline
is testable with no real book files and no hardware.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from ebooklib import epub


def _make_epub(path: Path, title: str = "Test Book", author: str = "A. Author") -> None:
    book = epub.EpubBook()
    book.set_identifier("id-test-001")
    book.set_title(title)
    book.set_language("en")
    book.add_author(author)

    chapters = []
    for n in (1, 2):
        ch = epub.EpubHtml(title=f"Chapter {n}", file_name=f"chap_{n}.xhtml", lang="en")
        ch.content = (
            f"<html><body><h1>Chapter {n}</h1>"
            f"<p>First paragraph of chapter {n}.</p>"
            f"<p>Second paragraph of chapter {n}.</p>"
            "<script>console.log('drop me')</script>"
            "</body></html>"
        )
        book.add_item(ch)
        chapters.append(ch)

    book.toc = tuple(chapters)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ["nav", *chapters]

    epub.write_epub(str(path), book)


@pytest.fixture
def sample_epub(tmp_path: Path) -> Path:
    path = tmp_path / "sample.epub"
    _make_epub(path)
    return path


@pytest.fixture
def converted_dir(tmp_path: Path) -> Path:
    d = tmp_path / "converted"
    d.mkdir()
    return d
