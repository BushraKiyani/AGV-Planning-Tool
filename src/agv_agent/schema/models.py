from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional
from dataclasses import fields as dc_fields


@dataclass
class Evidence:
    snippet: Optional[str] = None
    source_tool: Optional[str] = None
    source_id: Optional[str] = None


@dataclass
class AGVSpec:
    # minimal canonical schema (extend as needed)
    source_id: Optional[str] = None
    tool_trace: list[str] = field(default_factory=list)

    device_name: Optional[str] = None
    vendor: Optional[str] = None

    length_mm: Optional[float] = None
    width_mm: Optional[float] = None
    height_mm: Optional[float] = None

    payload_kg: Optional[float] = None
    speed_m_s: Optional[float] = None
    weight_kg: Optional[float] = None
    turning_radius_mm: Optional[float] = None
    lift_height_mm: Optional[float] = None

    # evidence/confidence per field (kept internal but exported)
    _evidence: Dict[str, Evidence] = field(default_factory=dict)
    _confidence: Dict[str, float] = field(default_factory=dict)


    def to_row_dict(self) -> dict:
        """
        Serialize AGVSpec into a flat row for CSV export.
        """
        row = {}

        # Export all canonical fields
        for f in dc_fields(self):
            name = f.name
            if name.startswith("_"):
                continue
            row[name] = getattr(self, name)

        # Evidence
        for k, ev in self._evidence.items():
            row[f"evidence_{k}"] = getattr(ev, "snippet", None)
            row[f"source_{k}"] = getattr(ev, "source_tool", None)

        # Confidence
        for k, conf in self._confidence.items():
            row[f"confidence_{k}"] = conf

        # Tool trace
        row["tool_trace"] = ",".join(self.tool_trace) if self.tool_trace else None

        return row


@dataclass
class AGVSpecCandidate:
    """
    Intermediate representation from each tool before normalization/validation.
    fields: canonical field names -> values
    """
    source_id: str
    tool: str
    fields: Dict[str, Any] = field(default_factory=dict)
    confidence: Dict[str, float] = field(default_factory=dict)
    evidence: Dict[str, Evidence] = field(default_factory=dict)

    @staticmethod
    def from_flat_dict(d: Dict[str, Any], source_id: str, tool: str) -> "AGVSpecCandidate":
        # Accept vendor/device naming if present
        fields = {}
        for k, v in d.items():
            if k in {"device", "device_name"}:
                fields["device_name"] = v
            elif k == "vendor":
                fields["vendor"] = v
            else:
                # keep raw for normalize() to interpret
                fields[k] = v
        conf = {k: 0.65 for k in fields.keys()}
        ev = {k: Evidence(snippet=None, source_tool=tool, source_id=source_id) for k in fields.keys()}
        return AGVSpecCandidate(source_id=source_id, tool=tool, fields=fields, confidence=conf, evidence=ev)

    @staticmethod
    def from_key_values(kv: Dict[str, str], source_id: str, tool: str) -> "AGVSpecCandidate":
        # Store raw kv in fields; normalize() will map synonyms.
        fields = {"_kv": kv}
        conf = {"_kv": 0.55}
        preview = "; ".join([f"{k}: {v}" for k, v in list(kv.items())[:5]])
        ev = {"_kv": Evidence(snippet=preview, source_tool=tool, source_id=source_id)}
        return AGVSpecCandidate(source_id=source_id, tool=tool, fields=fields, confidence=conf, evidence=ev)

