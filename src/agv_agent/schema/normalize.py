from __future__ import annotations

import re
from typing import Any, Dict, Optional, Tuple

from agv_agent.schema.models import AGVSpecCandidate, Evidence


def _to_float(s: str) -> Optional[float]:
    if s is None:
        return None
    s = str(s)
    s = s.replace(",", ".")
    m = re.search(r"[-+]?\d+(\.\d+)?", s)
    return float(m.group(0)) if m else None


def _parse_agilox_number(s: str) -> Optional[float]:
    """
    Extract the first number from an AGILOX field string, applying the German
    thousands-separator rule: a period followed by exactly 3 digits is a
    thousands separator, not a decimal point.
      "1.511"              -> 1511.0   (raw token from dimensions)
      "1.000 KG (2.2 lbs)" -> 1000.0  (payload annotated string)
      "2.100 MM (82.7 in)" -> 2100.0  (turning radius annotated string)
      "810"                -> 810.0   (plain integer, < 1000, no separator)
      "214 KG"             -> 214.0   (plain integer)
    """
    if not s or s == "NA":
        return None
    m = re.search(r"\d+(?:[.,]\d+)?", str(s))
    if not m:
        return None
    token = m.group(0)
    if re.fullmatch(r"\d{1,3}\.\d{3}", token):
        return float(token.replace(".", ""))
    return _to_float(token)


def _parse_dimensions_mm(text: str) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """
    Parse patterns like:
      "1500 x 800 x 1200 mm" or "1500x800x1200MM"
      "1.511 x 810 x 1.862 MM"  (AGILOX: German thousands-sep, 1.511 = 1511 mm)
    """
    t = text.lower().replace("×", "x")
    nums = re.findall(r"\d+(?:[.,]\d+)?", t)
    if len(nums) >= 3:
        return _parse_agilox_number(nums[0]), _parse_agilox_number(nums[1]), _parse_agilox_number(nums[2])
    return None, None, None


def normalize_candidate(c: AGVSpecCandidate) -> AGVSpecCandidate:
    """
    Map tool outputs into canonical fields + convert units.
    """
    fields = dict(c.fields)

    # If tool produced raw KV dict
    kv = fields.get("_kv")
    if isinstance(kv, dict):
        # very light synonym mapping (extend in configs/schema.yaml later)
        for k, v in kv.items():
            kl = k.lower()

            if "abmess" in kl or "abmasse" in kl or "dimensions" in kl:
                l, w, h = _parse_dimensions_mm(v)
                fields["length_mm"] = l
                fields["width_mm"] = w
                fields["height_mm"] = h

            if "trag" in kl or "payload" in kl or "last" in kl:
                fields["payload_kg"] = _to_float(v)

            if "geschwind" in kl or "speed" in kl:
                # if in m/s already -> float
                fields["speed_m_s"] = _to_float(v)

            if "eigengewicht" in kl or "weight" in kl:
                fields["weight_kg"] = _to_float(v)

            if "drehkreis" in kl or "turn" in kl:
                fields["turning_radius_mm"] = _to_float(v)

            if "hubh" in kl or "lift" in kl:
                fields["lift_height_mm"] = _to_float(v)

    # If regex_agilox produced abmasse field
    if "abmasse" in fields and isinstance(fields["abmasse"], str):
        l, w, h = _parse_dimensions_mm(fields["abmasse"])
        fields["length_mm"] = fields.get("length_mm") or l
        fields["width_mm"] = fields.get("width_mm") or w
        fields["height_mm"] = fields.get("height_mm") or h
    # Map common AGILOX regex fields into canonical ones (if present).
    # Use _parse_agilox_number so German thousands-sep values (e.g. "1.000 KG" = 1000)
    # are converted correctly instead of being read as decimals.
    if isinstance(fields.get("max_last"), str) and fields.get("payload_kg") is None:
        fields["payload_kg"] = _parse_agilox_number(fields["max_last"])

    if isinstance(fields.get("eigengewicht"), str) and fields.get("weight_kg") is None:
        fields["weight_kg"] = _parse_agilox_number(fields["eigengewicht"])

    if isinstance(fields.get("drehkreis"), str) and fields.get("turning_radius_mm") is None:
        fields["turning_radius_mm"] = _parse_agilox_number(fields["drehkreis"])

    if isinstance(fields.get("max_hubhoehe"), str) and fields.get("lift_height_mm") is None:
        fields["lift_height_mm"] = _parse_agilox_number(fields["max_hubhoehe"])

    # Device/vendor naming normalization
    if "device_name" not in fields and "device" in fields:
        fields["device_name"] = fields.get("device")
    if "vendor" not in fields and "vendor" in c.fields:
        fields["vendor"] = c.fields["vendor"]

    c.fields = fields
    return c
