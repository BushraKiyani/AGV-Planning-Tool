from __future__ import annotations

import logging
from dataclasses import asdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

from agv_agent.agent.merge import merge_candidates
from agv_agent.agent.scoring import completeness_score
from agv_agent.ingest.pdf_reader import read_pdf_text
from agv_agent.ingest.web_scraper import scrape_vendor_devices
from agv_agent.schema.models import AGVSpecCandidate
from agv_agent.schema.normalize import normalize_candidate
from agv_agent.schema.validate import validate_candidate
from agv_agent.utils.io import iter_inputs, write_output_table

# Extractors
from agv_agent.extract.regex_agilox import extract_agilox_from_text
from agv_agent.extract.key_value import extract_key_values_from_text
from agv_agent.extract.regex_generic import extract_features_from_text
from agv_agent.extract.llm_extractor import extract_with_llm


LOGGER = logging.getLogger("agv_orchestrator")


def _looks_like_agilox(text: str) -> bool:
    t = text.lower()
    return ("agilox" in t) or ("nfk" in t) or ("drehkreis" in t) or ("eigengewicht" in t)


def _tool_plan_for_text(text: str) -> List[str]:
    """
    Decide tool order. This is the 'agent policy'.
    """
    if _looks_like_agilox(text):
        return ["regex_agilox", "key_value", "llm"]
    return ["key_value", "regex_generic", "llm"]


def _run_tool(tool: str, text: str, source_id: str, llm_backend: str) -> List[AGVSpecCandidate]:
    """
    Each tool returns list of AGVSpecCandidate(s) (e.g., multi-device).
    """
    if tool == "regex_agilox":
        df = extract_agilox_from_text(text, split_sections=True)
        cands = []
        for _, row in df.iterrows():
            cands.append(AGVSpecCandidate.from_flat_dict(row.to_dict(), source_id=source_id, tool=tool))
        return cands

    if tool == "regex_generic":
        # Generic feature list: useful when you know which fields you want.
        # Keep minimal default list; you can expand via config later.
        wanted = ["dimensions", "payload", "speed", "weight", "turning radius"]
        d = extract_features_from_text(text, wanted)
        return [AGVSpecCandidate.from_flat_dict(d, source_id=source_id, tool=tool)]

    if tool == "key_value":
        kv = extract_key_values_from_text(text)
        return [AGVSpecCandidate.from_key_values(kv, source_id=source_id, tool=tool)]

    if tool == "llm":
        # LLM tries to fill normalized schema fields.
        llm_out = extract_with_llm(text=text, backend=llm_backend)
        return [AGVSpecCandidate.from_flat_dict(llm_out, source_id=source_id, tool=tool)]

    raise ValueError(f"Unknown tool: {tool}")


def _extract_from_pdf(pdf_path: Path) -> Tuple[str, str]:
    text, stats = read_pdf_text(pdf_path, engine="auto")
    source_id = pdf_path.name
    return text, source_id


def _extract_from_txt(txt_path: Path) -> Tuple[str, str]:
    text = txt_path.read_text(encoding="utf-8", errors="ignore")
    source_id = txt_path.name
    return text, source_id


def run_extraction_auto(
    input_path: str,
    output_path: Path,
    min_completeness: float = 0.60,
    max_steps: int = 4,
    llm_backend: str = "none",
) -> pd.DataFrame:
    """
    Agent-like loop:
    - Iterate inputs (single file, folder, or URL)
    - For each input, choose tool plan and run tools until completeness reached
    - Merge results, normalize, validate
    - Save a final CSV table
    """
    rows: List[Dict] = []

    # URL mode (scraper is already structured)
    if input_path.lower().startswith(("http://", "https://")):
        LOGGER.info("URL input detected -> using web scraper first: %s", input_path)
        df = scrape_vendor_devices(input_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(output_path, index=False)
        return df

    # File/folder mode
    for path in iter_inputs(input_path):
        if path.suffix.lower() == ".pdf":
            text, source_id = _extract_from_pdf(path)
        elif path.suffix.lower() in {".txt", ".text"}:
            text, source_id = _extract_from_txt(path)
        else:
            LOGGER.warning("Skipping unsupported: %s", path)
            continue

        LOGGER.info("Processing: %s", source_id)

        tools = _tool_plan_for_text(text)
        if llm_backend == "none":
            tools = [t for t in tools if t != "llm"]
        tools = tools[:max_steps]

        candidates: List[AGVSpecCandidate] = []

        for step, tool in enumerate(tools, start=1):
            LOGGER.info("Step %d/%d - tool=%s", step, len(tools), tool)
            new_cands = _run_tool(tool, text, source_id, llm_backend)
            # normalize + validate + score each candidate
            for c in new_cands:
                c2 = normalize_candidate(c)
                c3 = validate_candidate(c2)
                candidates.append(c3)

            best = merge_candidates(candidates)
            score = completeness_score(best)
            LOGGER.info("Completeness after %s: %.2f", tool, score)

            if score >= min_completeness:
                LOGGER.info("Threshold reached (%.2f >= %.2f).", score, min_completeness)
                break

        final = merge_candidates(candidates)
        rows.append(final.to_row_dict())

    df_out = pd.DataFrame(rows)
    write_output_table(df_out, output_path)
    return df_out
