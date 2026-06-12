# AGV Planning Tool (agv-agent)

AGV Planning Tool is a Python CLI that extracts and normalizes Automated Guided Vehicle (AGV) specifications from unstructured documents and vendor web pages. It combines deterministic parsing, vendor-aware regex extraction, optional LLM fallback, and confidence-based merging to generate structured, audit-ready CSV outputs for downstream planning workflows.

## Why this matters

Industrial AGV specifications are typically distributed as heterogeneous PDFs or web catalogs. 
This tool reduces manual extraction effort by converting unstructured specifications into a standardized, machine-readable format suitable for planning, comparison, and analytics pipelines.

## What the project does

The tool ingests either:

- a **single PDF/TXT file**,
- a **folder of PDFs/TXTs**, or
- a **vendor products URL**.

For document inputs, it runs an "agent-like" pipeline that selects extraction tools, evaluates completeness, and stops early once a configurable threshold is reached. The final output is a table of canonical AGV fields (dimensions, payload, speed, etc.) plus traceability metadata such as evidence snippets, confidence values, and tool history.

For URL inputs, it uses a web scraper to discover product/device pages and extract structured specifications directly from HTML tables/definition lists.

## Key capabilities

- **Multi-source ingestion**
  - PDF text extraction with PyMuPDF first and PyPDF2 fallback.
  - TXT ingestion with UTF-8-safe loading.
  - URL scraping for product catalogs and device pages.

- **Agent-style orchestration**
  - Dynamic tool plan selection per document.
  - Early stopping based on completeness score.
  - Maximum extraction steps per file.

- **Hybrid extraction stack**
  - Generic key/value extraction from text.
  - Generic regex-based feature extraction.
  - AGILOX-specific parser with section splitting (e.g., NFK / ONE).
  - Optional LLM extraction (`openai` or local HTTP endpoint).

- **Schema normalization + validation**
  - Synonym mapping from raw keys to canonical schema.
  - Unit-friendly numeric parsing.
  - Basic plausibility checks that reduce confidence on implausible values.

- **Confidence-aware merge and auditability**
  - Field-level merge by highest confidence.
  - Evidence + source tool tracking.
  - Tool trace persisted into output.

## Architecture

```text
src/agv_agent/
  agent/
    orchestrator.py   # core pipeline loop, tool policy, stop conditions
    merge.py          # confidence-based field merge
    scoring.py        # completeness scoring over core fields

  extract/
    key_value.py      # key:value parser helpers
    regex_generic.py  # generic regex feature extraction
    regex_agilox.py   # AGILOX-focused extraction patterns
    llm_extractor.py  # optional OpenAI/local LLM fallback

  ingest/
    pdf_reader.py     # PDF extraction utilities and corpus builders
    web_scraper.py    # vendor/product page scraping + spec extraction

  schema/
    models.py         # AGVSpec and AGVSpecCandidate dataclasses
    normalize.py      # canonical field mapping and value conversion
    validate.py       # simple plausibility checks

  utils/
    io.py             # input iteration + CSV writing
    logging.py        # logging setup
    config.py         # JSON config loader

  cli.py              # command-line interface entry point
```

## Canonical output schema

The normalized output targets the following canonical fields:

- `source_id`, `tool_trace`
- `device_name`, `vendor`
- `length_mm`, `width_mm`, `height_mm`
- `payload_kg`, `speed_m_s`, `weight_kg`
- `turning_radius_mm`, `lift_height_mm`

Depending on extraction quality and source format, output may also include:

- `evidence_<field>`
- `source_<field>`
- `confidence_<field>`

## How extraction flow works

### 1) Input routing

- If `--input` is a URL, the scraper path is used.
- Otherwise the tool iterates local files:
  - PDFs first,
  - then TXTs that do not duplicate a PDF stem.

### 2) Tool plan selection

For each document, the orchestrator chooses a tool order:

- AGILOX-like text → `regex_agilox` → `key_value` → `llm`
- Other text → `key_value` → `regex_generic` → `llm`

When `--llm none` is used (default), LLM steps are removed.

### 3) Normalize + validate + score

Each candidate is:

1. normalized to canonical fields,
2. validated with basic plausibility checks,
3. merged into a best-so-far spec,
4. scored for completeness over core fields.

Core completeness fields:

- `device_name`
- `length_mm`, `width_mm`, `height_mm`
- `payload_kg`
- `speed_m_s`

The loop stops early once `--min-completeness` is reached or `--max-steps` is exhausted.

## Installation

### Requirements

- Python 3.10+
- Dependencies:
  - `pandas`
  - `requests`
  - `beautifulsoup4`
  - `PyPDF2`
  - `pymupdf`

### Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

This installs the CLI command `agv-agent`.

## CLI usage

### Basic extraction from a file

```bash
agv-agent extract \
  --input ./documents/spec_sheet.pdf \
  --output ./outputs/specs.csv
```

### Batch extraction from a folder

```bash
agv-agent extract \
  --input ./documents/ \
  --output ./outputs/specs.csv
```

### Scrape from a products URL

```bash
agv-agent extract \
  --input https://vendor.example.com/products \
  --output ./outputs/vendor_specs.csv
```

### Tune stopping and logging

```bash
agv-agent extract \
  --input ./documents/ \
  --output ./outputs/specs.csv \
  --min-completeness 0.75 \
  --max-steps 3 \
  --log DEBUG
```

### Enable LLM fallback (OpenAI)

```bash
export OPENAI_API_KEY=your_key
export OPENAI_MODEL=gpt-4o-mini   # optional

agv-agent extract \
  --input ./documents/spec_sheet.pdf \
  --output ./outputs/specs.csv \
  --llm openai
```
### Enable LLM fallback (local endpoint)

```bash
export LOCAL_LLM_URL=http://localhost:8000/generate

agv-agent extract \
  --input ./documents/spec_sheet.pdf \
  --output ./outputs/specs.csv \
  --llm local
```

## Design principles

- Deterministic first, LLM second
- Field-level confidence scoring
- Early stopping for efficiency
- Transparent tool traceability

## Notes and limitations

- URL mode returns scraped tabular data directly and does not currently run the full normalization/merge loop used for document mode.
- Synonym mapping and validation are intentionally lightweight and are meant to be extended as your dataset grows.
- Regex extractors are deterministic but source-format-sensitive; vendor-specific tuning improves recall.
- LLM support is optional and gracefully no-ops when required environment variables are missing.
- Fields such as `weight_kg`, `speed_m_s`, and `lift_height_mm` are not always present in every vendor brochure format. When a regex pattern finds no match, the field is left as `NaN` in the output — this reflects genuinely missing data, not an extraction error.

## Testing

Install the test dependencies and run pytest from the project root:

```bash
pip install -e ".[test]"
python -m pytest
```

The test suite covers `_parse_agilox_number` and `_parse_dimensions_mm` in `schema/normalize.py`, including the German thousands-separator format used in AGILOX brochures (where `"1.511"` means 1511 mm, not 1.511 mm).

## Development quick reference

- CLI: `src/agv_agent/cli.py`
- Orchestration: `src/agv_agent/agent/orchestrator.py`
- Schema/normalization: `src/agv_agent/schema/`
- Web scraping: `src/agv_agent/ingest/web_scraper.py`

## License

MIT — see [LICENSE](LICENSE).
