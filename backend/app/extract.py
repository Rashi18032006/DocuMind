"""Turn an uploaded file into plain text, keeping page numbers where the format has them."""

from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import PurePath

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}


class ExtractionError(ValueError):
    """The file can't be turned into usable text (wrong type, empty, scanned, corrupt)."""


@dataclass(frozen=True)
class Page:
    number: int | None  # None for formats without pages (DOCX, TXT)
    text: str


def extract_pages(filename: str, data: bytes) -> list[Page]:
    ext = PurePath(filename).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        supported = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        raise ExtractionError(f"Unsupported file type '{ext or 'none'}'. Upload one of: {supported}.")
    if not data:
        raise ExtractionError("The file is empty.")

    if ext == ".pdf":
        pages = _pdf(data)
    elif ext == ".docx":
        pages = _docx(data)
    else:
        pages = [Page(None, _decode(data))]

    pages = [Page(p.number, _clean(p.text)) for p in pages]
    pages = [p for p in pages if p.text]
    if not pages:
        raise ExtractionError(
            "No readable text found. If this is a scanned PDF, run it through OCR first."
        )
    return pages


def _pdf(data: bytes) -> list[Page]:
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError

    try:
        reader = PdfReader(io.BytesIO(data))
        return [Page(i + 1, page.extract_text() or "") for i, page in enumerate(reader.pages)]
    except (PdfReadError, ValueError) as exc:
        raise ExtractionError("This PDF couldn't be read. It may be corrupt or password-protected.") from exc


def _docx(data: bytes) -> list[Page]:
    from docx import Document

    try:
        doc = Document(io.BytesIO(data))
    except Exception as exc:  # python-docx raises several unrelated types for bad files
        raise ExtractionError("This DOCX file couldn't be read.") from exc
    parts = [p.text for p in doc.paragraphs]
    for table in doc.tables:
        for row in table.rows:
            parts.append(" | ".join(cell.text for cell in row.cells))
    return [Page(None, "\n".join(parts))]


def _decode(data: bytes) -> str:
    for encoding in ("utf-8", "utf-16", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ExtractionError("The text file's encoding isn't supported.")


def _clean(text: str) -> str:
    lines = [" ".join(line.split()) for line in text.replace("\x00", "").splitlines()]
    out: list[str] = []
    for line in lines:
        if line or (out and out[-1]):  # collapse runs of blank lines into one
            out.append(line)
    return "\n".join(out).strip()
