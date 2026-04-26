#!/usr/bin/env bash
# 单条 RQ1 抽样：SWE-bench Lite `pallets__flask-4045`，需本机已准备仓库与 API key。
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CODE_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DEFAULT_FLASK="${CODE_ROOT}/.rq1_repos/flask"
export CONCORD_SWE_REPO_ROOT="${CONCORD_SWE_REPO_ROOT:-$DEFAULT_FLASK}"

if [[ ! -d "${CONCORD_SWE_REPO_ROOT}/.git" ]]; then
  echo "未找到仓库: ${CONCORD_SWE_REPO_ROOT}"
  echo "请先按 rq1_runner --print-meta 的提示 clone 并 checkout，或设 CONCORD_SWE_REPO_ROOT。"
  exit 1
fi
if [[ -z "${OPENAI_API_KEY:-}" && -z "${ANTHROPIC_API_KEY:-}" ]]; then
  echo "请设置 OPENAI_API_KEY 或 ANTHROPIC_API_KEY（OpenAI 兼容端可设 OPENAI_BASE_URL）。" >&2
  exit 1
fi

cd "$CODE_ROOT"
# 单条、两种条件；若只想跑 ConcordCoder 可传第三参数：--conditions concordcoder
python3 scripts/rq1_runner.py \
  --instance-id pallets__flask-4045 \
  --out-dir results/rq1 \
  --conditions concordcoder,baseline \
  "$@"
