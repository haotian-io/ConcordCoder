# ConcordCoder

**Languages:** [English](README.md) | [中文](README.zh-CN.md) | [日本語](README.ja.md)

> **Cognitive-alignment–assisted code generation** — help users and the model form a *shared* understanding of the existing system *before* generating code, then co-produce an implementation.

## Repository layout

This repository is the installable Python package. After cloning, work from the repository root (where `pyproject.toml` lives) and run `pip install -e .`.

Assets outside this repository (e.g. a separate paper checkout) are not required at runtime.

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

## Documentation

- **[Evaluation & benchmarks](docs/EVALUATION.md)** — SWE-bench Lite driver, `mini_eval`, probing / logprobs tables, and reproducibility pointers (all paths in-repo).
- First-time API check: `concord doctor` (verifies keys / client init; no chat call).

## Environment variables

**`concord run` / `once` / `align` and `scripts/mini_eval.py` require an LLM**: set `OPENAI_API_KEY` or `ANTHROPIC_API_KEY`; the CLI exits with an error if neither is available (no stub generation).

For **OpenAI-compatible proxies**, set the API base URL (adjust path per your provider, often ending in `/v1`):

```bash
export OPENAI_API_KEY=sk-...
export OPENAI_BASE_URL=https://example.com/v1
# export ANTHROPIC_API_KEY=sk-ant-...
```

## Usage

### `concord once` (single task, good for scripts / CI)

By default, **batch LLM cognitive alignment** runs (`LLMAlignmentDialogue.run_batch`, consistent with paper Phase~2). Use **`--no-full-align`** only for fast regression, cost savings, or CI checks (extraction-side constraints + rule-based alignment).

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

**InlineCoder-style anchor path** (optional): narrow to a file/symbol, build a
draft anchor and upstream/downstream assembly (`--use-anchor`).

```bash
concord once /path/to/repo -t "..." -o /tmp/out --format markdown_plan \
  --target-file src/my_module.py \
  --symbol my_function \
  --use-anchor

# Optional: probing summary on the anchor draft (uses mock logprobs if the API
# does not return logprobs; requires --use-anchor)
concord once /path/to/repo -t "..." -o /tmp/out --format markdown_plan \
  --target-file src/my_module.py \
  --symbol my_function \
  --use-anchor --with-probe
```

**Mini evaluation (`mini_eval.py`):** runs three variants on a **real repo you
supply** plus **task YAMLs you supply**; prints one JSON object to stdout. No
sample project is bundled; see [`examples/mini_eval/README.md`](examples/mini_eval/README.md) ([zh](examples/mini_eval/README.zh-CN.md) · [ja](examples/mini_eval/README.ja.md)).

```bash
cd /path/to/ConcordCoder
export CONCORD_EVAL_REPO_ROOT=/abs/path/to/your/repo
export CONCORD_EVAL_TASKS_DIR=/abs/path/to/your/task_yamls
python3 scripts/mini_eval.py
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

## Research questions (summary)

Formal definitions, human-study protocol, and full claims appear in the **accompanying paper**. This repository ships **reproducible drivers** for the automated track; see [docs/EVALUATION.md](docs/EVALUATION.md).

- **RQ1:** Code generation quality (e.g. SWE-bench–style repository tasks).
- **RQ2:** Impact on user understanding (subjective and objective measures in the paper).
- **RQ3:** Cost–benefit of alignment dialogue (turns vs. downstream effort).
