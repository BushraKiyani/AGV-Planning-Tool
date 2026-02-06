from __future__ import annotations

from agv_agent.schema.models import AGVSpecCandidate


def validate_candidate(c: AGVSpecCandidate) -> AGVSpecCandidate:
    """
    Basic sanity checks; downgrades confidence if values are implausible.
    Keep simple for portfolio; extend later.
    """
    f = c.fields

    def penalize(key: str, factor: float = 0.5) -> None:
        if key in c.confidence:
            c.confidence[key] *= factor

    # Plausibility ranges (very rough)
    if isinstance(f.get("payload_kg"), (int, float)) and f["payload_kg"] is not None:
        if f["payload_kg"] <= 0 or f["payload_kg"] > 100000:
            penalize("payload_kg")

    for dim in ["length_mm", "width_mm", "height_mm"]:
        v = f.get(dim)
        if isinstance(v, (int, float)) and v is not None:
            if v <= 0 or v > 50000:
                penalize(dim)

    return c
