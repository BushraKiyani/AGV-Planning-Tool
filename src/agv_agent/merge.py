from __future__ import annotations

from dataclasses import fields as dc_fields
from typing import List

from agv_agent.schema.models import AGVSpecCandidate, AGVSpec


def merge_candidates(candidates: List[AGVSpecCandidate]) -> AGVSpec:
    """
    Merge policy:
    - Only write to canonical AGVSpec fields (prevents junk keys like 'abmasse')
    - Prefer higher confidence per canonical field
    - Keep evidence/confidence
    """
    merged = AGVSpec()
    if not candidates:
        return merged

    canonical = {f.name for f in dc_fields(AGVSpec) if not f.name.startswith("_")}

    best = {}  # field -> (conf, val, evidence)
    for cand in candidates:
        for field, val in cand.fields.items():
            if field not in canonical:
                continue  # ignore non-canonical keys like "_kv", "abmasse", etc.
            if val is None:
                continue

            conf = cand.confidence.get(field, 0.0)
            ev = cand.evidence.get(field)

            if field not in best or conf > best[field][0]:
                best[field] = (conf, val, ev)

    for field, (conf, val, ev) in best.items():
        setattr(merged, field, val)
        if ev is not None:
            merged._evidence[field] = ev
        merged._confidence[field] = conf

    merged.source_id = candidates[-1].source_id
    merged.tool_trace = [c.tool for c in candidates]
    return merged
