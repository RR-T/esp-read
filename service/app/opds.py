"""OPDS 1.x Atom acquisition feed.

CrossPoint's OpdsParser is a streaming, namespace-tolerant Atom parser. Per
<entry> it needs a <title>, optionally <author><name> and <id>, and a book link
`rel="…opds-spec.org/acquisition…" type="application/epub+zip" href="…"`. Cover
art and per-entry pagination are not parsed, so we keep the feed minimal but
valid OPDS/Atom.

hrefs are absolute (built from the request base URL) so the reader's downloader
doesn't have to resolve them relative to the feed URL.
"""

from __future__ import annotations

from xml.sax.saxutils import escape, quoteattr

from .models import LibraryIndex

ACQUISITION_REL = "http://opds-spec.org/acquisition"
EPUB_MEDIA_TYPE = "application/epub+zip"
FEED_TYPE = "application/atom+xml;profile=opds-catalog;kind=acquisition"

# Our own namespace for extensions the base OPDS spec doesn't cover. CrossPoint's
# parser is namespace-tolerant and ignores unknown elements, so this is safe to
# emit today and lets the device verify the download against the hash once the
# firmware grows a post-download integrity check (plan §3.2).
ESP_NS = "urn:esp-read"


def _entry(book, base_url: str, updated_iso: str) -> str:
    author = (
        f"\n    <author><name>{escape(book.author)}</name></author>"
        if book.author
        else ""
    )
    href = f"{base_url}/book/{book.id}.epub"
    return (
        "  <entry>\n"
        f"    <title>{escape(book.title)}</title>\n"
        f"    <id>urn:esp-read:book:{escape(book.id)}</id>\n"
        f"    <updated>{updated_iso}</updated>"
        f"{author}\n"
        f"    <link rel={quoteattr(ACQUISITION_REL)} "
        f"type={quoteattr(EPUB_MEDIA_TYPE)} href={quoteattr(href)}\n"
        f"          length={quoteattr(str(book.size_bytes))}/>\n"
        f"    <esp:sha256>{escape(book.sha256)}</esp:sha256>\n"
        "  </entry>"
    )


def build_catalog(index: LibraryIndex, *, base_url: str, updated_iso: str) -> str:
    """Render the full acquisition catalog as an OPDS Atom document string."""
    base_url = base_url.rstrip("/")
    entries = "\n".join(_entry(b, base_url, updated_iso) for b in index.books)
    self_href = f"{base_url}/opds"
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<feed xmlns="http://www.w3.org/2005/Atom" '
        'xmlns:opds="http://opds-spec.org/2010/catalog" '
        f'xmlns:esp="{ESP_NS}">\n'
        "  <id>urn:esp-read:catalog</id>\n"
        "  <title>esp-read Library</title>\n"
        f"  <updated>{updated_iso}</updated>\n"
        f"  <link rel=\"self\" href={quoteattr(self_href)} type={quoteattr(FEED_TYPE)}/>\n"
        f"{entries}\n"
        "</feed>\n"
    )
