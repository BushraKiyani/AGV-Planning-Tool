from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import pandas as pd

try:
    import PyPDF2
except ImportError as e:
    raise ImportError("PyPDF2 is required. Install with: pip install pypdf2") from e


PathLike = Union[str, Path]


# -----------------------------
# IO helpers
# -----------------------------
def read_pdf(path: PathLike) -> str:
    """Extract text from PDF using PyPDF2."""
    path = Path(path)
    with path.open("rb") as f:
        reader = PyPDF2.PdfReader(f)
        parts = []
        for page in reader.pages:
            parts.append(page.extract_text() or "")
    return "\n".join(parts)


def read_text(path: PathLike) -> str:
    """Read plain text (utf-8)."""
    return Path(path).read_text(encoding="utf-8", errors="ignore")


def load_text(path: PathLike) -> str:
    """Load text from a .pdf or .txt path based on suffix."""
    p = Path(path)
    if p.suffix.lower() == ".pdf":
        return read_pdf(p)
    elif p.suffix.lower() in {".txt", ".text"}:
        return read_text(p)
    else:
        raise ValueError(f"Unsupported file type: {p.suffix}. Use .pdf or .txt")


# -----------------------------
# Regex helpers
# -----------------------------
def _find_first(pattern: str, text: str, flags: int = re.IGNORECASE | re.DOTALL) -> Optional[str]:
    """
    Return first capture group if available, else full match.
    """
    m = re.search(pattern, text, flags)
    if not m:
        return None
    return (m.group(1) if m.lastindex else m.group(0)).strip()


def _normalize_ws(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


# -----------------------------
# AGILOX device sectioning
# -----------------------------
@dataclass(frozen=True)
class SectionDef:
    name: str
    start_pattern: str  # regex
    end_pattern: Optional[str] = None  # regex


def split_agilox_sections(text: str) -> Dict[str, str]:
    """
    Split brochure text into device-specific sections (NFK, ONE).
    Uses stronger header anchors when possible.
    """
    # Stronger anchors (you can tune these based on your extracted text)
    anchors = [
        ("AGILOX Narrowfork (NFK)", r"\bNFK\b|\bNarrowfork\b"),
        ("AGILOX ONE", r"\bAGILOX\s*ONE\b|\bONE\b"),
    ]

    hits: List[Tuple[int, str]] = []
    for name, pat in anchors:
        for m in re.finditer(pat, text, flags=re.IGNORECASE):
            hits.append((m.start(), name))
            break  # only first hit per device to avoid false splits

    if not hits:
        return {"AGILOX (full_text)": text}

    hits.sort(key=lambda x: x[0])

    out: Dict[str, str] = {}
    for i, (pos, name) in enumerate(hits):
        end = hits[i + 1][0] if i + 1 < len(hits) else len(text)
        out[name] = text[pos:end]

    return out



# -----------------------------
# AGILOX patterns (core)
# -----------------------------
AGILOX_PATTERNS: Dict[str, str] = {
    # German brochure fields — based on your legacy scripts
    "ABMASSE": r"ABMASSE\s*\(L\s*X\s*B\s*X\s*H\)\s*([0-9\.\sxX]+MM\s*\([0-9\.\sxX]+in\))",
    "EIGENGEWICHT": r"EIGENGEWICHT\s*([0-9]+KG\s*\([0-9]+\s*lbs\))",
    "MAX_LAST": r"MAX\.?\s*LAST\s*([0-9\s,\.]+KG\s*\([0-9\s,\.]+\s*lbs\))",
    "MAX_HUBHOEHE": r"MAX\.?\s*HUBH[ÖO]HE\s*([0-9\s,\.]+MM\s*\([0-9\s,\.]+in\))",
    "MAX_STATIONSHOEHE_EPAL": r"MAX\.?\s*STATIONSH[ÖO]HE\s*\(EPAL\)\s*([0-9\s,\.]+MM\s*\([0-9\s,\.]+in\))",
    "DREHKREIS": r"DREHKREIS\s*([0-9\s,\.]+MM\s*\([0-9\s,\.]+in\))",
    "MIN_GANGBREITE": r"MIN\.?\s*GANGBREITE\s*([0-9\s,\.]+MM\s*\([0-9\s,\.]+in\))",
    "MIN_DURCHFAHRTSBREITE": r"MIN\.?\s*DURCHFAHRTSBREITE\s*([0-9\s,\.]+MM\s*\([0-9\s,\.]+in\))",
    "LADEZEIT": r"LADEZEIT\s*([0-9\s\.]+Min\.\s*laden\s*=\s*[0-9]+\s*h\s*Betrieb)",
}


def extract_agilox_specs(text: str, device_name: str = "AGILOX") -> Dict[str, str]:
    """
    Extract AGILOX specs from a text chunk.
    Returns a stable dict of fields.
    """
    row: Dict[str, str] = {"vendor": "AGILOX", "device": device_name}

    for field, pat in AGILOX_PATTERNS.items():
        val = _find_first(pat, text)
        row[field.lower()] = _normalize_ws(val) if val else "NA"

    return row


def extract_agilox_from_text(text: str, split_sections: bool = True) -> pd.DataFrame:
    """
    Extract AGILOX specs from raw text.
    If split_sections=True, tries to split into NFK and ONE sections first.
    Returns one row per detected device/section.
    """
    if split_sections:
        sections = split_agilox_sections(text)
    else:
        sections = {"AGILOX (full_text)": text}

    rows = []
    for device_name, section_text in sections.items():
        rows.append(extract_agilox_specs(section_text, device_name=device_name))

    return pd.DataFrame(rows)


def extract_agilox_from_file(path: PathLike, split_sections: bool = True) -> pd.DataFrame:
    """
    Load a .pdf or .txt and extract AGILOX specs.
    """
    text = load_text(path)
    return extract_agilox_from_text(text, split_sections=split_sections)


# -----------------------------
# OPTIONAL: FTS Move patterns (if you want them in same file)
# -----------------------------
FTS_MOVE_PATTERNS: Dict[str, str] = {
    # These are tolerant defaults; refine after you test on your brochure text.
    "abmessungen": r"Abmessungen:\s*([0-9\sxX]+mm\s*\(LxBxH\))",
    "tragfaehigkeit": r"Tragf[aä]higkeit:\s*([0-9]+\s*kg.*)",
    "hubhoehe": r"Hubh[öo]he\s*(?:von)?\s*([0-9]+\s*mm)",
    "hoechstgeschwindigkeit": r"H[öo]chstgeschwindigkeit:\s*([0-9\.,]+\s*m/s.*)",
    "navigation": r"(nat[üu]rlicher\s+Navigation)",
    "batterie_management": r"(Autonomes\s+Batterie-Management)",
    "lithium_ionen_akkus": r"Lithium-Ionen-Akkus.*\(([^\)]*)\)",
    "sicherheitsscanner": r"Sicherheitsscanner.*?([0-9\-]+\s*Grad.*)",
    "ladestation": r"Ladestation.*?(autonom(?:en)?\s+Aufladen.*)",
    "zertifizierung": r"Zertifizierung:\s*([A-Za-z0-9\-]+)",
}


def extract_fts_move_specs(text: str, device_name: str = "FTS Move") -> Dict[str, str]:
    row: Dict[str, str] = {"vendor": "WEWO/FTS", "device": device_name}
    for field, pat in FTS_MOVE_PATTERNS.items():
        val = _find_first(pat, text)
        row[field] = _normalize_ws(val) if val else "NA"
    return row


# -----------------------------
# Convenience: multi-vendor extraction from a single file
# -----------------------------
def extract_known_devices_from_file(path: PathLike) -> pd.DataFrame:
    """
    Convenience helper if you sometimes have combined corpora.
    - Always tries AGILOX extraction
    - Also tries FTS Move patterns on the same text corpus

    Returns concatenated DataFrame.
    """
    text = load_text(path)

    dfs = [extract_agilox_from_text(text, split_sections=True)]

    # If FTS terms exist, attempt extraction
    if re.search(r"\bFTS\b|\bMove\b|WEWO", text, flags=re.IGNORECASE):
        fts_row = extract_fts_move_specs(text, device_name="FTS Move Standard")
        dfs.append(pd.DataFrame([fts_row]))

    return pd.concat(dfs, ignore_index=True)
