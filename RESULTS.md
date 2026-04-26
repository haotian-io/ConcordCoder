# Reproducibility and evaluation status

This file summarizes **what this repository guarantees for replication** and where to find the full procedures. Formal research questions, human-study design, and paper claims are documented in the **accompanying paper** and in [docs/EXPERIMENT_PROTOCOL_V1.md](docs/EXPERIMENT_PROTOCOL_V1.md). For driver-level details, see [docs/EVALUATION.md](docs/EVALUATION.md).

## Automated tests

| Item | Command | Expected |
|------|---------|----------|
| Unit tests | `python3 -m pytest -q` | All tests pass (CI and local should match; run from the repository root next to `pyproject.toml`). |

## RQ1 driver (SWE-bench Lite helper scripts)

The scripts `scripts/rq1_runner.py` and `scripts/rq1_analyze.py` implement a **documented** comparison workflow (ConcordCoder vs. baselines) on instances from the SWE-bench Lite metadata. They require:

1. **Dataset**: local Parquet for the split (default path relative to this repo: `../SWE-bench_Lite/data/…`) or set `SWE_BENCH_LOCAL_DIR`. See [docs/EVALUATION.md](docs/EVALUATION.md).
2. **Target repository**: each instance must be checked out at the instance `base_commit`. The recommended layout is a local clone under `.rq1_repos/<repo>/` (ignored by git; not distributed with the repo). Use `python3 scripts/rq1_runner.py --print-meta --instance-id <id>` for the exact `git clone` / `git checkout` commands.
3. **LLM credentials**: `OPENAI_API_KEY` or `ANTHROPIC_API_KEY`. For OpenAI-compatible endpoints, set `OPENAI_BASE_URL` as required by your provider.

**Non-LLM checks** (no API key): `--print-meta` and `--dry-run` validate metadata resolution and spec construction for a given `--instance-id`.

**Full run** (requires keys and a prepared repo): see [results/rq1/README.md](results/rq1/README.md) and `scripts/run_rq1_sample.sh`.

## Outputs

After a successful run, JSON artifacts are written under `results/rq1/` (filename derived from `instance_id`). Optional plots and CSV summaries are produced by `scripts/rq1_analyze.py`. **We do not commit large result JSON or plots by default**; generate them locally for your replication or paper tables.

## Paper assets (sibling `Paper/` checkout)

The pipeline overview figure in the paper source uses `fig/overview_gpt.png` in the **paper** repository. This **Code** package does not ship the LaTeX tree; use Overleaf or a full TeX installation to build the paper (if a package such as `algorithmicx` is missing locally, install it or use the Overleaf project).

## Security

**Never commit API keys or tokens.** Use environment variables or your platform’s secret manager. If a key was ever committed to any repository, **revoke and rotate** it in the provider console.
