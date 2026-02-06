from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Dict, List, Tuple, Union

import pandas as pd

try:
    import fitz
except ImportError as e:
    raise ImportError("PyMuPDF is required for key-value PDF extraction. Install with: pip install pymupdf") from e


PathLike = Union[str, Path]


def extract_text_from_pdf_fitz(pdf_path: PathLike) -> str:
    """Extract text from all pages of a PDF using PyMuPDF (fitz)."""
    pdf_path = str(pdf_path)
    doc = fitz.open(pdf_path)
    parts: List[str] = []
    for page in doc:
        parts.append(page.get_text("text") or "")
    return "\n".join(parts)


def extract_key_values_from_text(text: str) -> Dict[str, str]:
    """
    Parse key-value pairs from extracted text:
      Key: Value
    Returns a dict (last occurrence wins).
    """
    kv: Dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue

        key, value = line.split(":", 1)
        key = re.sub(r"\s+", " ", key).strip()
        value = re.sub(r"\s+", " ", value).strip()

        # Heuristics to avoid junk keys (optional but helpful)
        if not key or not value:
            continue
        if len(key) > 80:
            continue

        kv[key] = value
    return kv


def extract_key_values_from_pdf(pdf_path: PathLike) -> Dict[str, str]:
    """Convenience wrapper: PDF -> text -> key-values dict."""
    text = extract_text_from_pdf_fitz(pdf_path)
    return extract_key_values_from_text(text)


def process_pdfs_in_folder(folder_path: PathLike) -> pd.DataFrame:
    """
    Batch helper (like your original):
    Reads all PDFs in folder and returns a single DataFrame with columns:
      source_id, key, value
    """
    folder_path = Path(folder_path)
    rows: List[Tuple[str, str, str]] = []

    for pdf in sorted(folder_path.glob("*.pdf")):
        text = extract_text_from_pdf_fitz(pdf)
        kv = extract_key_values_from_text(text)
        for k, v in kv.items():
            rows.append((pdf.name, k, v))

    return pd.DataFrame(rows, columns=["source_id", "key", "value"])
