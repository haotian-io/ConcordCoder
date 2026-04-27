# ConcordCoder

**Languages:** [English](README.md) | [中文](README.zh-CN.md) | [日本語](README.ja.md)

> **Cognitive-alignment–assisted code generation** — help users and the model form a *shared* understanding of the existing system *before* generating code, then co-produce an implementation.

## Repository layout

This repository is the **installable Python package**. After cloning, work from the repository root (where `pyproject.toml` lives) and run `pip install -e .`.

**Asset relationship:**
- This `Code/` directory is the standalone installable package.
- Parent directory (`ConcordCoder/`) also contains:
  - `Paper/` — LaTeX source and compiled PDF
  - `SWE-bench_Lite/` — Benchmark dataset
  - `USAGE.md` — Comprehensive usage guide
  - `experiments/` — Experimental repos and results

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
  Validated LLM code generation + cognitive summary
```

## Quick start

### 1. Installation

```bash
cd /path/to/ConcordCoder/Code
pip install -e ".[dev]"

# Optional: LLM backend
pip install -e ".[openai]"     # OpenAI (GPT-4o, GPT-5, etc.)
pip install -e ".[anthropic]"  # Anthropic Claude

# All optional dependencies
pip install -e ".[dev,all]"
```

### 2. Configure API keys

```bash
# OpenAI or compatible endpoint
export OPENAI_API_KEY='your-api-key'
export OPENAI_BASE_URL='https://api.openai.com/v1'  # or your proxy
export CONCORD_OPENAI_MODEL='gpt-4o'  # or 'gpt-5', etc.

# Anthropic
export ANTHROPIC_API_KEY='your-api-key'
```

### 3. Verify setup

```bash
concord doctor --backend openai
# Output: LLM client initialized (no network call)
```

### 4. Run your first task

```bash
concord once /path/to/your/repo \
  -t "Add exponential backoff retries to the payment processing function" \
  -o /tmp/concord_output \
  --format markdown_plan
```

## Core commands

### `concord once` — Single task (recommended for scripts/CI)

Runs the full pipeline and writes structured output.

```bash
# Markdown plan output
concord once /path/to/repo -t "Your task description" -o /tmp/out --format markdown_plan

# JSON output (machine-readable)
concord once /path/to/repo -t "..." -o /tmp/out --format json

# Unified diff only
concord once /path/to/repo -t "..." -o /tmp/out --format diff

# Fast mode (skip Git history and test analysis)
concord once /path/to/repo -t "..." -o /tmp/out --fast

# Anchor path (InlineCoder-style, for targeted functions)
concord once /path/to/repo -t "..." -o /tmp/out \
  --target-file src/module.py \
  --symbol function_name \
  --use-anchor

# Optional: run probing summary on anchor draft (requires --use-anchor)
concord once /path/to/repo -t "..." -o /tmp/out \
  --target-file src/module.py \
  --symbol function_name \
  --use-anchor --with-probe

# Use real chat logprobs in OpenAI (falls back to mock on failure)
# export CONCORD_REAL_LOGPROBS=1
```

### `concord extract` — Phase 1 only (no LLM required)

Extracts context without generating code.

```bash
concord extract /path/to/repo --task "Add caching to user queries"
concord extract /path/to/repo --task "..." --json context.json
```

### `concord run` — Full pipeline

```bash
# Non-interactive (batch alignment)
concord run /path/to/repo --task "..."

# Interactive dialogue
concord run /path/to/repo --task "..." --interactive

# Specify backend
concord run /path/to/repo --task "..." --backend openai
```

### `concord align` — Phase 2 only

Only runs alignment dialogue (for debugging).

```bash
concord align /path/to/repo --task "..."
```

## Environment variables

| Variable | Description | Required |
|----------|-------------|----------|
| `OPENAI_API_KEY` | OpenAI API key | For OpenAI backend |
| `ANTHROPIC_API_KEY` | Anthropic API key | For Claude backend |
| `OPENAI_BASE_URL` | API endpoint (for proxies) | Optional |
| `CONCORD_OPENAI_MODEL` | Model name (e.g. `gpt-4o`) | Default: `gpt-4o` |
| `CONCORD_REAL_LOGPROBS` | Use real logprobs (1=yes) | Optional |

## Evaluation & benchmarks

See **[docs/EVALUATION.md](docs/EVALUATION.md)** for:
- SWE-bench Lite driver (`scripts/swe_bench_batch.py`)
- Mini evaluation (`scripts/mini_eval.py`)
- Probing/logprobs hyperparameters
- Reproducibility guide

### Mini evaluation

For custom repos and task YAMLs, run regression testing:

```bash
cd /path/to/ConcordCoder  # repository root with pyproject.toml
export CONCORD_EVAL_REPO_ROOT=/abs/path/to/your/repo
export CONCORD_EVAL_TASKS_DIR=/abs/path/to/your/task_yamls
python3 scripts/mini_eval.py
```

See [`examples/mini_eval/README.md`](examples/mini_eval/README.md) for details.

## Code structure

```
src/concordcoder/
├── cli.py              # Typer CLI entry point
├── pipeline.py         # Main orchestration
├── schemas.py          # Pydantic data structures
├── llm_client.py      # LLM API client
├── extraction/         # Phase 1 modules
│   ├── bundle_builder.py
│   ├── ast_analyzer.py
│   ├── call_graph.py
│   ├── git_historian.py
│   └── test_extractor.py
├── alignment/          # Phase 2 modules
│   ├── dialogue.py
│   ├── llm_dialogue.py
│   └── prompts.py
└── generation/         # Phase 3 modules
    ├── constrained_gen.py
    ├── anchor_pipeline.py
    ├── probing.py
    └── stub.py
```

## Testing

```bash
pytest -v
```

All tests use `StubLLM` (no network required).

## Research questions

See the **accompanying paper** for full definitions:
- **RQ1:** Code generation quality (automated evaluation on SWE-bench Lite)
- **RQ2:** User understanding and trust (planned user study)
- **RQ3:** Cost–benefit of alignment dialogue (planned)

## Documentation index

| Document | Description |
|----------|-------------|
| **[docs/EVALUATION.md](docs/EVALUATION.md)** | Evaluation protocols and reproducibility |
| **[docs/MINI_EVAL_RUNBOOK.md](docs/MINI_EVAL_RUNBOOK.md)** | Mini evaluation guide |
| **../USAGE.md** | Comprehensive usage guide (multi-language) |
| **../Paper/** | LaTeX source and compiled PDF |
| **../experiments/results/** | RQ1 experimental results |