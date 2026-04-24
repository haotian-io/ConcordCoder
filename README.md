# ConcordCoder

**Languages:** [English](README.md) | [中文](README.zh-CN.md) | [日本語](README.ja.md)

> **Cognitive-alignment–assisted code generation** — help users and the model form a *shared* understanding of the existing system *before* generating code, then co-produce an implementation.

## Repository layout

This repository is the installable Python package. After cloning, work from the repository root (where `pyproject.toml` lives) and run `pip install -e .`.

Research assets (papers, session logs, or parent-folder notes) are not required at runtime; they are optional context for the project narrative.

## Core pipeline

```
User task
   ↓
[Phase 1] Context extraction
  AST + call graph + Git history + test hints → ContextBundle
   ↓
[Phase 2] Alignment dialogue
  Human–AI rounds (rebuild context → confirm constraints → co-design) → AlignmentRecord
   ↓
[Phase 3] Constrained generation
  Validated LLM code generation + short cognitive summary
```

## Setup

Use a virtual environment (venv or conda is fine):

```bash
cd /path/to/ConcordCoder
pip install -e ".[dev]"

# Optional: LLM backend (one of)
pip install -e ".[openai]"     # OpenAI (e.g. GPT-4o)
pip install -e ".[anthropic]"  # Anthropic Claude

# Optional: Git history features
pip install -e ".[git]"

# All optional runtime deps
pip install -e ".[dev,all]"
```

## Environment variables

```bash
export OPENAI_API_KEY=sk-...         # OpenAI
export ANTHROPIC_API_KEY=sk-ant-...  # Anthropic
```

## Usage

### `concord once` (single task, good for scripts / CI)

By default, **no** multi-turn LLM alignment: lightweight constraints from extraction + rule-based alignment (low latency). Use `--full-align` for the full **batch** LLM alignment step.

```bash
pip install -e ".[dev,openai]"   # or anthropic

# Writes result.json; for markdown, also plan.md; for json_files, files/ and raw_model_output.txt
concord once /path/to/target/repo \
  -t "Describe the change" \
  -o /tmp/concord_out \
  --format markdown_plan

# Machine-readable JSON: {"files":[{"path","content"}]} → parsed under files/
concord once /path/to/repo -t "..." -o /tmp/out --format json

# Unified diff only → diff.patch
concord once /path/to/repo -t "..." -o /tmp/out --format diff

# Fast context extraction (smaller scan, skip Git + test pass)
concord once /path/to/repo -t "..." -o /tmp/out --fast
```

`--format` accepts: `markdown_plan` | `md` | `json` / `json_files` | `diff` / `unified_diff`.

### Phase 1: `extract` (context only)

```bash
concord extract /path/to/repo --task "Add exponential backoff retries to the payment path"

# Dump ContextBundle to JSON
concord extract /path/to/repo --task "..." --json context.json
```

### Full pipeline: `run` (Phase 1 → 2 → 3)

```bash
# Batch (non-interactive) alignment
concord run /path/to/repo --task "Add exponential backoff retries to the payment path"

# Interactive alignment dialogue
concord run /path/to/repo --task "..." --interactive

# LLM backend
concord run /path/to/repo --task "..." --backend openai
concord run /path/to/repo --task "..." --backend anthropic
```

### `align` only (Phase 2, debugging)

```bash
concord align /path/to/repo --task "..."
```

## Code layout

```
src/concordcoder/
├── schemas.py
├── pipeline.py
├── cli.py
├── llm_client.py
├── extraction/
│   ├── bundle_builder.py
│   ├── ast_analyzer.py
│   ├── call_graph.py
│   ├── git_historian.py
│   └── test_extractor.py
├── alignment/
│   ├── dialogue.py
│   ├── llm_dialogue.py
│   └── prompts.py
└── generation/
    ├── stub.py
    ├── json_output.py
    ├── anchor_pipeline.py
    └── constrained_gen.py
```

## Tests

```bash
pytest -v
```

Covers, among other things: AST/call graph/test extraction, `BundleBuilder`, alignment stubs, `ConstrainedGenerator` stubs, end-to-end pipeline, JSON output parsing, and `concord once`–related helpers.

## Research

See [`docs/research_plan.md`](docs/research_plan.md).

- **RQ1:** Does ConcordCoder improve code generation quality (e.g. SWE-bench–style evals)?
- **RQ2:** Subjective and objective impact on user understanding?
- **RQ3:** Cost–benefit of dialogue (turns vs. edit/debug cycles)?
