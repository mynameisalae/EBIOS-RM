"""Word vers PDF : réutilise ce qui est à jour, et dit clairement quand aucune suite bureautique n'est disponible."""

from __future__ import annotations

import os

import pytest

from ebios_rm.reporting import pdf


def test_an_up_to_date_pdf_is_reused_without_calling_any_office_suite(tmp_path, monkeypatch):
    docx = tmp_path / "r.docx"
    docx.write_bytes(b"word")
    existing = tmp_path / "r.pdf"
    existing.write_bytes(b"%PDF")
    os.utime(existing, (docx.stat().st_mtime + 10,) * 2)
    monkeypatch.setattr(pdf, "_libreoffice", lambda: pytest.fail("must not be called"))
    assert pdf.convert_to_pdf(docx) == existing


def test_a_stale_pdf_is_made_again(tmp_path, monkeypatch):
    docx = tmp_path / "r.docx"
    docx.write_bytes(b"word")
    old = tmp_path / "r.pdf"
    old.write_bytes(b"old")
    os.utime(old, (docx.stat().st_mtime - 10,) * 2)
    monkeypatch.setattr(pdf, "_libreoffice", lambda: "soffice")
    monkeypatch.setattr(pdf, "_with_libreoffice", lambda office, src, dst: dst.write_bytes(b"new"))
    assert pdf.convert_to_pdf(docx).read_bytes() == b"new"


def test_no_office_suite_is_a_plain_message_not_a_crash(tmp_path, monkeypatch):
    docx = tmp_path / "r.docx"
    docx.write_bytes(b"word")
    monkeypatch.setattr(pdf, "_libreoffice", lambda: None)
    monkeypatch.setattr(pdf.sys, "platform", "linux")
    with pytest.raises(pdf.PdfUnavailable, match="installez LibreOffice"):
        pdf.convert_to_pdf(docx)


def test_a_failing_conversion_is_reported_as_unavailable(tmp_path, monkeypatch):
    import subprocess

    docx = tmp_path / "r.docx"
    docx.write_bytes(b"word")
    monkeypatch.setattr(pdf, "_libreoffice", lambda: "soffice")

    def boom(*args, **kwargs):
        raise subprocess.CalledProcessError(1, "soffice")

    monkeypatch.setattr(pdf, "_with_libreoffice", boom)
    with pytest.raises(pdf.PdfUnavailable, match="a échoué"):
        pdf.convert_to_pdf(docx)
