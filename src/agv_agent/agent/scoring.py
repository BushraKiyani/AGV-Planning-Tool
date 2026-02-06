from __future__ import annotations

from agv_agent.schema.models import AGVSpec


CORE_FIELDS = [
    "device_name",
    "length_mm",
    "width_mm",
    "height_mm",
    "payload_kg",
    "speed_m_s",
]


def completeness_score(spec: AGVSpec) -> float:
    filled = 0
    for f in CORE_FIELDS:
        v = getattr(spec, f, None)
        if v is None:
            continue
        if isinstance(v, str) and not v.strip():
            continue
        filled += 1
    return filled / len(CORE_FIELDS)
