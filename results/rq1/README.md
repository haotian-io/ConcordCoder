# RQ1 outputs (`results/rq1/`)

This directory is the **default output location** for `scripts/rq1_runner.py`. Files here are **not** part of the source distribution; create them on your machine when replicating the RQ1 workflow described in [docs/EVALUATION.md](../docs/EVALUATION.md).

## What gets written

- **JSON** — one file per run, named from `instance_id` (characters such as `/` are normalized in the filename). Each file lists conditions run (e.g. ConcordCoder vs. baseline), timing, `fairness_budget`, `cost` fields, and model outputs as documented in the script and schema.
- **Plots / CSV** (optional) — produced by `scripts/rq1_analyze.py` into a subfolder you choose (e.g. `results/rq1/plots/`).

## One-command sample (illustrative instance)

The helper script [scripts/run_rq1_sample.sh](../scripts/run_rq1_sample.sh) runs a **single** SWE-bench Lite instance (`pallets__flask-4045`) with two conditions, after you have:

1. Cloned the target repo and checked out the `base_commit` for that instance (use `python3 scripts/rq1_runner.py --print-meta --instance-id pallets__flask-4045` for the exact commands).
2. Set `CONCORD_SWE_REPO_ROOT` to that clone (default in the script: `<repo root>/.rq1_repos/flask` if you follow the meta instructions).
3. Set `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` (and `OPENAI_BASE_URL` if using a compatible gateway).

```bash
cd /path/to/this/repository
export CONCORD_SWE_REPO_ROOT="$PWD/.rq1_repos/flask"
export OPENAI_API_KEY=...
./scripts/run_rq1_sample.sh
```

## Post-processing

```bash
python3 scripts/rq1_analyze.py --results-dir results/rq1 --out-dir results/rq1/plots
```

Requires at least one valid `*.json` from the runner. If no JSON is present, the analyzer exits with a clear message (see script help).

## Validate `rq1_analyze` without an LLM (plotting smoke test)

Copy the committed schema example, then run the analyzer (numbers are **synthetic**; replace with real `rq1_runner` output for any paper table):

```bash
cp experiments/rq1_smoke_for_analyze.json results/rq1/
python3 scripts/rq1_analyze.py --results-dir results/rq1 --out-dir results/rq1/plots
```

## Five demo instances: meta only (no LLM)

To print `git clone` / `git checkout` for every id in `experiments/swe_tiny_config.yaml` (one real `rq1_runner` run still needs a separate checkout per id):

```bash
bash scripts/rq1_tiny_meta_loop.sh
```

## Reference instance

`pallets__flask-4045` is used in documentation as a **smoke** example only; the full benchmark and scaling process are described in [docs/EVALUATION.md](../docs/EVALUATION.md).
