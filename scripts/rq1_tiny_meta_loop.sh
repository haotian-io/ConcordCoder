#!/usr/bin/env bash
# For each instance in experiments/swe_tiny_config.yaml, run rq1_runner --print-meta (no API key).
set -euo pipefail
CODE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$CODE_ROOT"
mapfile -t IDS < <(python3 - <<'PY'
import yaml
from pathlib import Path
p = Path("experiments/swe_tiny_config.yaml")
for iid in yaml.safe_load(p.read_text()).get("instance_ids", []):
    print(iid)
PY
)
for iid in "${IDS[@]}"; do
  echo ""
  echo "================================================================"
  echo "instance: $iid"
  echo "================================================================"
  python3 scripts/rq1_runner.py --print-meta --instance-id "$iid"
done
