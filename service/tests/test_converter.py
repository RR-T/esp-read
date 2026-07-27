"""End-to-end conversion tests against a synthetic EPUB."""

from __future__ import annotations

from pathlib import Path

from app import device_format as fmt
from app.converter import compute_book_id, convert_epub


def test_convert_produces_meta_and_content(sample_epub: Path, converted_dir: Path):
    meta = convert_epub(sample_epub, converted_dir)

    assert meta.title == "Test Book"
    assert meta.author == "A. Author"
    assert meta.language == "en"
    assert meta.format == fmt.FORMAT_VERSION
    assert meta.chapter_count == 2
    assert meta.chapters[0].title == "Chapter 1"

    out_dir = converted_dir / meta.id
    assert (out_dir / fmt.META_FILENAME).exists()
    content = (out_dir / fmt.CONTENT_FILENAME).read_bytes()
    assert len(content) == meta.content_bytes


def test_scripts_are_stripped(sample_epub: Path, converted_dir: Path):
    meta = convert_epub(sample_epub, converted_dir)
    content = (converted_dir / meta.id / fmt.CONTENT_FILENAME).read_text("utf-8")
    assert "drop me" not in content
    assert "First paragraph of chapter 1." in content


def test_chapter_offsets_are_byte_accurate(sample_epub: Path, converted_dir: Path):
    meta = convert_epub(sample_epub, converted_dir)
    content = (converted_dir / meta.id / fmt.CONTENT_FILENAME).read_bytes()

    # Chapters separated by a single FORM FEED.
    assert content.count(fmt.CHAPTER_BREAK.encode()) == meta.chapter_count - 1

    # Each recorded start offset lands on the heading mark for that chapter.
    for chapter in meta.chapters:
        assert content[chapter.start : chapter.start + 1] == fmt.HEADING_MARK.encode()


def test_conversion_is_cached_and_deterministic(sample_epub: Path, converted_dir: Path):
    first = convert_epub(sample_epub, converted_dir)
    second = convert_epub(sample_epub, converted_dir)  # hits the cache
    assert first.id == second.id == compute_book_id(sample_epub)
    assert first.model_dump() == second.model_dump()
