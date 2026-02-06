# AGV Planning Tool (AGV Agent)

An agent-like pipeline that extracts and normalizes Automated Guided Vehicle (AGV) technical specifications from unstructured PDFs, TXT files, or vendor product pages. It combines rule-based parsing, vendor-specific regex, and optional LLM fallback to produce a clean CSV of normalized fields.

## Features

- **Multi-source ingestion**: PDFs, plain text files, folders of documents, or vendor product listing URLs.
- **Agent-style tool orchestration**: Runs multiple extraction tools until a completeness threshold is met.
- **Vendor-aware parsing**: Includes AGILOX-specific regex for common spec formats.
- **Schema normalization**: Maps raw key/value pairs to canonical fields (dimensions, payload, speed, etc.).
- **Optional LLM fallback**: OpenAI or local endpoint can fill missing values when enabled.
- **CSV output**: Produces a consistent table for downstream analysis.

## Project Structure

```
src/agv_agent/
  agent/           # Orchestration, merging, scoring
  extract/         # Regex and LLM-based extractors
  ingest/          # PDF reader + vendor web scraper
  schema/          # Canonical schema, normalization, validation
  utils/           # IO, logging, configuration helpers
  cli.py           # Command-line interface
```

## Installation

### Requirements

- Python 3.10+
- Dependencies: `pandas`, `requests`, `beautifulsoup4`, `PyPDF2`, `pymupdf`

### Install locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

This installs the CLI entry point as `agv-agent`.

## Usage

### Extract from a PDF or folder

```bash
agv-agent extract \
  --input ./documents/spec_sheet.pdf \
  --output ./outputs/specs.csv
```

```bash
agv-agent extract \
  --input ./documents/ \
  --output ./outputs/specs.csv
```

### Extract from a URL (vendor product page)

```bash
agv-agent extract \
  --input https://vendor.example.com/products \
  --output ./outputs/vendor_specs.csv
```

### Tune extraction behavior

```bash
agv-agent extract \
  --input ./documents/ \
  --output ./outputs/specs.csv \
  --min-completeness 0.75 \
  --max-steps 3 \
  --log DEBUG
```

### Optional LLM fallback

Enable OpenAI fallback (requires `OPENAI_API_KEY`):

```bash
export OPENAI_API_KEY=your_key
export OPENAI_MODEL=gpt-4o-mini  # optional override

agv-agent extract \
  --input ./documents/spec_sheet.pdf \
  --output ./outputs/specs.csv \
  --llm openai
```

Enable a local LLM service (requires `LOCAL_LLM_URL`):

```bash
export LOCAL_LLM_URL=http://localhost:8000/generate

agv-agent extract \
  --input ./documents/spec_sheet.pdf \
  --output ./outputs/specs.csv \
  --llm local
```

## Output Schema

The normalized CSV includes canonical fields (as available):

- `device_name`, `vendor`
- `length_mm`, `width_mm`, `height_mm`
- `payload_kg`, `speed_m_s`, `weight_kg`
- `turning_radius_mm`, `lift_height_mm`

It also includes optional evidence and confidence columns (prefixed with `evidence_`, `source_`, `confidence_`) to help trace extraction decisions.

## How It Works

1. **Ingest** input PDFs, TXT files, or scrape vendor product pages.
2. **Tool selection** chooses an extraction plan (key/value parsing, regex, LLM) based on document content.
3. **Normalization** maps raw fields to canonical schema and converts values to numeric units where possible.
4. **Scoring** tracks completeness; tools stop early once the threshold is met.
5. **Merge + export** outputs a single CSV with one row per device or document.

## Development Notes

- Main CLI entry point: `src/agv_agent/cli.py`
- Orchestration logic: `src/agv_agent/agent/orchestrator.py`
- Schema + normalization: `src/agv_agent/schema/`
- Vendor scraping logic: `src/agv_agent/ingest/web_scraper.py`

## License

No license specified.
