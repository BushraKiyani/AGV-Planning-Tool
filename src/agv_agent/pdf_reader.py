from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

LOGGER = logging.getLogger("agv_pdf_reader")

PathLike = Union[str, Path]


@dataclass(frozen=True)
class TextStats:
    pages: int
    characters: int
    words: int


def _basic_stats(text: str, pages: int) -> TextStats:
    words = len(text.split())
    return TextStats(pages=pages, characters=len(text), words=words)


def read_pdf_text(pdf_path: PathLike, engine: str = "auto") -> Tuple[str, TextStats]:
    """
    Extract text from a PDF.

    engine:
      - "auto": try PyMuPDF (fitz) first, fallback to PyPDF2
      - "fitz": force PyMuPDF
      - "pypdf2": force PyPDF2
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(str(pdf_path))

    if engine not in {"auto", "fitz", "pypdf2"}:
        raise ValueError("engine must be one of: auto, fitz, pypdf2")

    # Try PyMuPDF (fitz) first (often best)
    if engine in {"auto", "fitz"}:
        try:
            import fitz  # PyMuPDF

            doc = fitz.open(str(pdf_path))
            parts: List[str] = []
            for page in doc:
                parts.append(page.get_text("text") or "")
            text = "\n".join(parts)
            stats = _basic_stats(text, pages=doc.page_count)
            return text, stats
        except Exception as e:
            if engine == "fitz":
                raise
            LOGGER.debug("PyMuPDF failed for %s: %s (falling back to PyPDF2)", pdf_path.name, e)

    # Fallback: PyPDF2
    try:
        import PyPDF2

        with pdf_path.open("rb") as f:
            reader = PyPDF2.PdfReader(f)
            parts = []
            for page in reader.pages:
                parts.append(page.extract_text() or "")
            text = "\n".join(parts)
            stats = _basic_stats(text, pages=len(reader.pages))
            return text, stats
    except Exception as e:
        raise RuntimeError(f"Failed to extract text from {pdf_path}") from e


def write_pdf_text(pdf_path: PathLike, out_txt_path: PathLike, engine: str = "auto") -> TextStats:
    """
    Extract text from a PDF and write to a .txt file.
    Returns text stats.
    """
    text, stats = read_pdf_text(pdf_path, engine=engine)
    out_txt_path = Path(out_txt_path)
    out_txt_path.parent.mkdir(parents=True, exist_ok=True)
    out_txt_path.write_text(text, encoding="utf-8", errors="ignore")
    return stats


def convert_folder_pdfs_to_txt(
    folder: PathLike,
    out_dir: PathLike,
    engine: str = "auto",
    pattern: str = "*.pdf",
) -> Dict[str, TextStats]:
    """
    Convert all PDFs in `folder` into individual .txt files in `out_dir`.
    Returns a dict: {pdf_filename: stats}.
    """
    folder = Path(folder)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    stats_map: Dict[str, TextStats] = {}
    pdfs = sorted(folder.glob(pattern))

    for pdf in pdfs:
        out_txt = out_dir / (pdf.stem + ".txt")
        stats = write_pdf_text(pdf, out_txt, engine=engine)
        stats_map[pdf.name] = stats

    return stats_map


def build_combined_corpus(
    folder: PathLike,
    engine: str = "auto",
    pattern: str = "*.pdf",
    separator: str = "\n\n" + "=" * 80 + "\n\n",
) -> Tuple[str, Dict[str, TextStats]]:
    """
    Read all PDFs in a folder and return a single combined text corpus.
    Also returns per-file stats.
    """
    folder = Path(folder)
    pdfs = sorted(folder.glob(pattern))

    chunks: List[str] = []
    stats_map: Dict[str, TextStats] = {}

    for pdf in pdfs:
        text, stats = read_pdf_text(pdf, engine=engine)
        stats_map[pdf.name] = stats
        header = f"[FILE: {pdf.name}]"
        chunks.append(header + "\n" + text)

    combined = separator.join(chunks)
    return combined, stats_map


def write_combined_corpus(
    folder: PathLike,
    out_txt_path: PathLike,
    engine: str = "auto",
    pattern: str = "*.pdf",
) -> Dict[str, TextStats]:
    """
    Build a combined corpus from all PDFs in folder and write to out_txt_path.
    Returns per-file stats.
    """
    combined, stats_map = build_combined_corpus(folder, engine=engine, pattern=pattern)
    out_txt_path = Path(out_txt_path)
    out_txt_path.parent.mkdir(parents=True, exist_ok=True)
    out_txt_path.write_text(combined, encoding="utf-8", errors="ignore")
    return stats_map
