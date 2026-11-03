"""Split page text into overlapping chunks small enough to embed and cite."""

from __future__ import annotations

from dataclasses import dataclass

from .extract import Page


@dataclass(frozen=True)
class Chunk:
    index: int
    page: int | None
    text: str


def chunk_pages(pages: list[Page], size: int = 900, overlap: int = 150) -> list[Chunk]:
    if overlap >= size:
        raise ValueError("overlap must be smaller than size")

    chunks: list[Chunk] = []
    for page in pages:
        for piece in _split(page.text, size, overlap):
            chunks.append(Chunk(len(chunks), page.number, piece))
    return chunks


def _split(text: str, size: int, overlap: int) -> list[str]:
    """Pack paragraphs into windows of ~size chars; hard-split paragraphs that are too long."""
    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    limit = size - overlap - 1  # leaves room for the overlap tail in front of each piece
    units: list[str] = []
    for para in paragraphs:
        while len(para) > limit:
            cut = para.rfind(" ", 0, limit)
            cut = cut if cut > limit // 2 else limit
            units.append(para[:cut].strip())
            para = para[cut:].strip()
        if para:
            units.append(para)

    windows: list[str] = []
    current = ""
    for unit in units:
        candidate = f"{current}\n{unit}" if current else unit
        if len(candidate) <= size:
            current = candidate
            continue
        windows.append(current)
        tail = current[-overlap:]
        tail = tail[tail.find(" ") + 1 :] if " " in tail else tail  # start the overlap on a word
        current = f"{tail}\n{unit}" if len(tail) + len(unit) + 1 <= size else unit
    if current:
        windows.append(current)
    return windows
