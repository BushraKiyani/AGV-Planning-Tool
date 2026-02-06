from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, Optional
import logging


DEFAULT_FIELDS = [
    "device_name", "vendor",
    "length_mm", "width_mm", "height_mm",
    "payload_kg", "speed_m_s", "weight_kg",
    "turning_radius_mm", "lift_height_mm",
]


def _extract_json_block(text: str) -> Dict[str, Any]:
    m = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not m:
        return {}
    try:
        return json.loads(m.group(0))
    except Exception:
        return {}


def extract_with_llm(text: str, backend: str = "none", fields: Optional[list[str]] = None) -> Dict[str, Any]:
    """
    backend: "none" | "openai" | "local"
    """
    fields = fields or DEFAULT_FIELDS

    if backend == "none":
        return {}

    if backend == "openai":
        log = logging.getLogger("agv_llm")
        log.info("LLM backend=openai, OPENAI_API_KEY set? %s", bool(os.getenv("OPENAI_API_KEY")))
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return {}

        prompt = (
            "Extract AGV technical specifications from the text below.\n"
            "Return ONLY valid JSON with these keys:\n"
            f"{fields}\n\n"
            "Rules:\n"
            "- Use numbers for *_mm, *_kg, *_m_s\n"
            "- Use null if unknown\n\n"
            "TEXT:\n"
            f"{text[:12000]}"
        )

        try:
            from openai import OpenAI
            client = OpenAI(api_key=api_key)
            resp = client.chat.completions.create(
                model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
            )
            out = resp.choices[0].message.content or ""
            log.info("LLM raw response length: %d", len(out))
            return _extract_json_block(out)
        except Exception:
            return {}

    if backend == "local":
        # Placeholder hook: implement using your local model runner
        # Example: call a local HTTP endpoint or GPT4All python client
        # Must return JSON text or dict.
        local_url = os.getenv("LOCAL_LLM_URL")  # e.g. http://localhost:8000/generate
        if not local_url:
            return {}

        # Minimal HTTP call (optional)
        import requests
        payload = {"prompt": text[:8000], "fields": fields}
        try:
            r = requests.post(local_url, json=payload, timeout=60)
            r.raise_for_status()
            # Accept either dict response or text
            if isinstance(r.json(), dict):
                return r.json()
        except Exception:
            return {}

        return {}

    raise ValueError(f"Unknown LLM backend: {backend}")
