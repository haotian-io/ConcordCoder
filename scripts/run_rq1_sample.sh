#!/usr/bin/env bash
# RQ1 single-instance smoke run: SWE-bench Lite instance pallets__flask-4045.
# Requires: repo at instance base_commit (see rq1_runner.py --print-meta) and an LLM API key.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CODE_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DEFAULT_FLASK="${CODE_ROOT}/.rq1_repos/flask"
export CONCORD_SWE_REPO_ROOT="${CONCORD_SWE_REPO_ROOT:-$DEFAULT_FLASK}"

if [[ ! -d "${CONCORD_SWE_REPO_ROOT}/.git" ]]; then
  echo "Repository not found: ${CONCORD_SWE_REPO_ROOT}" >&2
  echo "Clone and checkout the base_commit from: python3 scripts/rq1_runner.py --print-meta --instance-id pallets__flask-4045" >&2
  echo "Or set CONCORD_SWE_REPO_ROOT to the checkout root." >&2
  exit 1
fi
if [[ -z "${OPENAI_API_KEY:-}" && -z "${ANTHROPIC_API_KEY:-}" ]]; then
  echo "Set OPENAI_API_KEY or ANTHROPIC_API_KEY. For OpenAI-compatible APIs, set OPENAI_BASE_URL as needed." >&2
  exit 1
fi

cd "$CODE_ROOT"
# Default: ConcordCoder + baseline. Override with e.g. --conditions concordcoder
python3 scripts/rq1_runner.py \
  --instance-id pallets__flask-4045 \
  --out-dir results/rq1 \
  --conditions concordcoder,baseline \
  "$@"
