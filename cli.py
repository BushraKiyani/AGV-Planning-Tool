from __future__ import annotations

import argparse
import logging
from pathlib import Path

from agv_agent.agent.orchestrator import run_extraction_auto
from agv_agent.utils.logging import setup_logging
from agv_agent.utils.io import write_output_table


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="agv-agent", description="AGV spec extraction (agent-like)")

    sub = p.add_subparsers(dest="cmd", required=True)

    # extract command
    p_extract = sub.add_parser("extract", help="Extract AGV specs from PDFs/TXTs/URLs")
    p_extract.add_argument("--input", required=True, help="Path to .pdf/.txt folder/file OR a URL")
    p_extract.add_argument("--output", default="specs.csv", help="Output CSV path")
    p_extract.add_argument("--mode", default="auto", choices=["auto"], help="Extraction mode")
    p_extract.add_argument("--min-completeness", type=float, default=0.60, help="Stop threshold [0..1]")
    p_extract.add_argument("--max-steps", type=int, default=4, help="Max tool attempts per document")
    p_extract.add_argument("--log", default="INFO", help="Log level: DEBUG/INFO/WARNING")
    p_extract.add_argument("--llm", default="none", choices=["none", "openai", "local"], help="LLM backend for fallback extraction")

    return p


def _is_url(s: str) -> bool:
    return s.lower().startswith(("http://", "https://"))


def main() -> None:
    args = build_parser().parse_args()
    setup_logging(args.log)

    if args.cmd == "extract":
        inp = args.input
        out = Path(args.output)

        df = run_extraction_auto(
            input_path=inp,
            output_path=out,
            min_completeness=args.min_completeness,
            max_steps=args.max_steps,
            llm_backend=args.llm
        )

        # df already written, but return value useful for quick debug
        logging.getLogger("agv_cli").info("Done. Rows=%d Columns=%d", len(df), len(df.columns))


if __name__ == "__main__":
    main()
