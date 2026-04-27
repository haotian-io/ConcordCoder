#!/usr/bin/env bash
set -euo pipefail

CODE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="${1:-$CODE_ROOT}"
OUT_DIR="${2:-/tmp/concord_demo_deepseek}"
TASK_TEXT="${3:-请概述这个仓库的 CLI 入口，并给出一个最小修改建议。}"

if [[ -z "${OPENAI_API_KEY:-}" ]]; then
  echo "ERROR: OPENAI_API_KEY is not set." >&2
  echo "Hint: export OPENAI_API_KEY='...'" >&2
  exit 1
fi

export OPENAI_BASE_URL="${OPENAI_BASE_URL:-https://api.deepseek.com/v1}"
export CONCORD_OPENAI_MODEL="${CONCORD_OPENAI_MODEL:-deepseek-chat}"

cd "$CODE_ROOT"
python3 -m concordcoder.cli doctor --backend openai
python3 -m concordcoder.cli once "$REPO_ROOT" \
  --task "$TASK_TEXT" \
  --out-dir "$OUT_DIR" \
  --format markdown_plan \
  --backend openai \
  --fast

echo
echo "Demo output written to: $OUT_DIR"
echo "  - $OUT_DIR/result.json"
echo "  - $OUT_DIR/plan.md"
