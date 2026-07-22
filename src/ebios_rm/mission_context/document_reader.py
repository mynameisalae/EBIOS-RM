"""Read supplied documents to plain text for ingestion (conception §11, extraction pipeline).

Supported out of the box: .txt/.md (native), .docx (via pandoc). .pdf is supported
when a PDF library is installed, and raises a clear, actionable error otherwise —
never a silent empty read (which would let real content vanish, §2).
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

SUPPORTED_SUFFIXES = {".txt", ".md", ".docx", ".pdf"}


class DocumentReadError(RuntimeError):
    """Raised when a document cannot be read to text — never swallowed."""


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _read_docx(path: Path) -> str:
    pandoc = shutil.which("pandoc")
    if pandoc is None:
        raise DocumentReadError(
            f"Reading {path.name} requires pandoc, which was not found on PATH. "
            "Install pandoc, or convert the document to .txt/.md first."
        )
    result = subprocess.run(
        [pandoc, str(path), "-t", "plain", "--wrap=none"],
        capture_output=True, text=True, encoding="utf-8",
    )
    if result.returncode != 0:
        raise DocumentReadError(f"pandoc failed to read {path.name}: {result.stderr.strip()}")
    return result.stdout


def _read_pdf(path: Path) -> str:
    try:
        import pdfplumber  # noqa: PLC0415 — optional dependency
    except ImportError as exc:
        raise DocumentReadError(
            f"Reading {path.name} requires a PDF library. Install it with "
            "`pip install pdfplumber`, or convert the PDF to text first."
        ) from exc
    with pdfplumber.open(str(path)) as pdf:
        return "\n".join((page.extract_text() or "") for page in pdf.pages)


def read_document(path: str | Path) -> str:
    """Return the plain text of a supported document (conception §11)."""
    path = Path(path)
    if not path.exists():
        raise DocumentReadError(f"Document not found: {path}")
    suffix = path.suffix.lower()
    if suffix in {".txt", ".md"}:
        return _read_text(path)
    if suffix == ".docx":
        return _read_docx(path)
    if suffix == ".pdf":
        return _read_pdf(path)
    raise DocumentReadError(
        f"Unsupported document type '{suffix}' for {path.name}. Supported: {sorted(SUPPORTED_SUFFIXES)}."
    )
