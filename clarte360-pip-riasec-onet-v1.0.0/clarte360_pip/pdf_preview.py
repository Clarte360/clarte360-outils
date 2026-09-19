from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path


def pdf_pages_as_png(pdf_bytes: bytes, first_page: int = 3, last_page: int = 4) -> list[bytes]:
    """Render selected PDF pages server-side with Poppler/pdftoppm."""
    if first_page < 1 or last_page < first_page:
        raise ValueError("Invalid PDF page range")
    with tempfile.TemporaryDirectory(prefix="clarte360_pip_preview_") as tmp:
        tmp_path = Path(tmp)
        pdf_path = tmp_path / "report.pdf"
        prefix = tmp_path / "page"
        pdf_path.write_bytes(pdf_bytes)
        try:
            proc = subprocess.run(
                [
                    "pdftoppm", "-png", "-r", "120",
                    "-f", str(first_page), "-l", str(last_page),
                    str(pdf_path), str(prefix),
                ],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=30,
            )
        except FileNotFoundError as exc:
            raise RuntimeError("Le moteur de prévisualisation PDF (pdftoppm) n'est pas installé.") from exc
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("La génération de la prévisualisation PDF a dépassé le délai autorisé.") from exc
        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout or "erreur inconnue").strip()
            raise RuntimeError(f"Impossible de rendre la prévisualisation PDF : {detail}")
        pages = [path.read_bytes() for path in sorted(tmp_path.glob("page-*.png"))]
        expected = last_page - first_page + 1
        if len(pages) != expected:
            raise RuntimeError(f"Prévisualisation PDF incomplète : {len(pages)} page(s) sur {expected} attendue(s).")
        return pages
