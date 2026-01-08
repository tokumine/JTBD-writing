# Gemini Writing Evaluation Framework

A comprehensive evaluation framework comparing Gemini 3.0 Pro/Flash against competing frontier LLMs on realistic professional writing tasks.

## Overview

This framework evaluates LLM writing capabilities using:
- **O*NET Database**: 18,000+ real professional writing tasks from the US Department of Labor
- **Diverse Personas**: Writers across industries, experience levels, and communication styles
- **Multiple Judges**: Claude Opus 4.5, GPT-5.2, and Gemini 3.0 Pro as independent evaluators
- **Rigorous Methodology**: Position shuffling, dual-persona judging, majority-of-majorities voting

## Quick Start

### Prerequisites

**System dependencies** (for PDF generation):

```bash
# macOS
brew install cairo pango gdk-pixbuf libffi

# Ubuntu/Debian
sudo apt-get install -y libcairo2 libpango-1.0-0 libgdk-pixbuf2.0-0 libffi-dev
```

### Installation

```bash
# Clone the repository
git clone https://github.com/your-org/gemini-writing-eval
cd gemini-writing-eval

# Install with pip
pip install -e ".[dev]"

# Set up environment
cp .env.example .env
# Edit .env and add your OPENROUTER_API_KEY
```

> **Note:** After installation, the `gemini-eval` command should be available. If not, either:
> - Restart your terminal/shell session
> - Use `python -m src.cli` as an alternative (e.g., `python -m src.cli run --preset smoke`)

### Run an Evaluation

```bash
# Quick smoke test (~$5, ~6 min)
gemini-eval run --preset smoke

# Development iteration (~$25, ~18 min)
gemini-eval run --preset dev

# Standard evaluation (~$800, ~4 hrs)
gemini-eval run --preset standard

# Get cost estimate without running
gemini-eval estimate --preset standard
```

## Preset Configurations

| Preset | Prompts | Est. Cost | Est. Time | Use Case |
|--------|---------|-----------|-----------|----------|
| smoke | 10 | ~$5 | 6 min | Verify pipeline works |
| dev | 30 | ~$25 | 18 min | Development iteration |
| quick | 100 | ~$150 | 1.5 hrs | Quick directional signal |
| standard | 200 | ~$800 | 4 hrs | Standard evaluation |
| comprehensive | 500 | ~$2,500 | 10 hrs | Publication-grade |
| full | 1000 | ~$8,000 | 24 hrs | Full rigorous evaluation |

## Features

### Writing Task Generation
- Extracts writing-relevant tasks from O*NET database
- Generates diverse personas with realistic backgrounds
- Grounds prompts in real companies and industries
- Supports attachments, reply threads, and constraints

### Evaluation Engine
- Pairwise comparisons (Gemini vs one competitor)
- Position-shuffled judging to eliminate bias
- Dual persona evaluation (writing expert + recipient)
- Best-of-N voting with multiple judges

### Analysis
- Win rates with confidence intervals
- Inter-judge agreement metrics (Cohen's Kappa)
- Bias detection (position, length, format)
- Weakness clustering and theme analysis

### TUI & Reporting
- Live progress dashboard
- Interactive results browser
- PDF analyst report with visualizations

## Project Structure

```
gemini-writing-eval/
├── src/
│   ├── cli.py              # Command-line interface
│   ├── config/             # Settings and presets
│   ├── data/               # O*NET extraction
│   ├── prompts/            # Prompt generation pipeline
│   ├── eval/               # Evaluation engine
│   ├── api/                # OpenRouter client
│   ├── storage/            # Database and checkpoints
│   ├── analysis/           # Statistics and analysis
│   ├── reports/            # PDF generation
│   └── tui/                # Terminal UI
├── db/
│   └── onet.db             # O*NET database
├── data/                   # Static data files
├── results/                # Evaluation outputs
└── tests/                  # Test suite
```

## CLI Commands

```bash
# Run evaluation
gemini-eval run --preset standard
gemini-eval run --prompts 100 --models gemini_pro,gpt_pro

# Resume interrupted evaluation
gemini-eval resume results/eval_2024-01-15_14-30-00/

# View results
gemini-eval view results/eval_2024-01-15_14-30-00/

# Generate report
gemini-eval report results/eval_2024-01-15_14-30-00/

# Export data
gemini-eval export results/eval_2024-01-15_14-30-00/ --format csv

# Validate setup
gemini-eval validate
```

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run tests with coverage
pytest --cov=src --cov-report=html

# Type checking
mypy src

# Linting
ruff check src tests
```

## License

MIT License
