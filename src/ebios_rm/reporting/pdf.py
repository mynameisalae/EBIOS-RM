"""Word to PDF, for sending a report to a client.

No new dependency: it asks the office suite already on the machine — LibreOffice if it is there, otherwise
Microsoft Word on Windows. When neither exists it says so plainly instead of failing obscurely.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

_LIBREOFFICE_PATHS = (
    r"C:\Program Files\LibreOffice\program\soffice.exe",
    r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
    "/Applications/LibreOffice.app/Contents/MacOS/soffice",
)
_WORD_SCRIPT = (
    "$w = New-Object -ComObject Word.Application; $w.Visible = $false; "
    "try { $d = $w.Documents.Open($env:EBIOS_SRC, $false, $true); $d.ExportAsFixedFormat($env:EBIOS_DST, 17); $d.Close($false) } "
    "finally { $w.Quit() }"
)
TIMEOUT_SECONDS = 180


class PdfUnavailable(RuntimeError):
    """No office suite could produce the PDF."""


def _libreoffice() -> str | None:
    found = shutil.which("soffice") or shutil.which("libreoffice")
    if found:
        return found
    return next((p for p in _LIBREOFFICE_PATHS if Path(p).exists()), None)


def _with_libreoffice(office: str, docx: Path, pdf: Path) -> None:
    subprocess.run([office, "--headless", "--convert-to", "pdf", "--outdir", str(pdf.parent), str(docx)],
                   check=True, capture_output=True, timeout=TIMEOUT_SECONDS)
    produced = pdf.parent / (docx.stem + ".pdf")
    if produced != pdf:
        produced.replace(pdf)


def _with_word(docx: Path, pdf: Path) -> None:
    env = {**os.environ, "EBIOS_SRC": str(docx.resolve()), "EBIOS_DST": str(pdf.resolve())}
    subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", _WORD_SCRIPT],
                   check=True, capture_output=True, timeout=TIMEOUT_SECONDS, env=env)


def convert_to_pdf(docx: str | Path, pdf: str | Path | None = None) -> Path:
    """The PDF of a Word file, made next to it unless a path is given. Reuses an up-to-date PDF."""
    source = Path(docx)
    target = Path(pdf) if pdf else source.with_suffix(".pdf")
    if target.exists() and target.stat().st_mtime >= source.stat().st_mtime:
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        office = _libreoffice()
        if office:
            _with_libreoffice(office, source, target)
        elif sys.platform == "win32":
            _with_word(source, target)
        else:
            raise PdfUnavailable("Pour produire un PDF, installez LibreOffice (ou Microsoft Word sous Windows).")
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as exc:
        raise PdfUnavailable("La conversion en PDF a échoué : vérifiez que Word ou LibreOffice s'ouvre sur cet ordinateur.") from exc
    if not target.exists():
        raise PdfUnavailable("La conversion en PDF n'a produit aucun fichier.")
    return target
