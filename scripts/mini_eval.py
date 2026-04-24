#!/usr/bin/env python3
"""
Mini evaluation: fixture tasklab × baseline variants, JSON to stdout.
Requires the same API keys as ``concord once`` (OPENAI_API_KEY and optional OPENAI_BASE_URL).

The printed JSON matches the paper (§Evaluation, RQ1, artifact-backed driver):
  Top level: "fixture_repo", "rows"
  Each row: task_id, task_yaml, variant (narrow_no_anchor | with_anchor |
            anchor_with_probe), dependency_level, use_anchor, with_probe,
            pytest{ran, exit_code, pass}, warnings_n, code_plan_len, probe, n_parsed_files

Usage (from package root, after pip install -e .):
  python3 scripts/mini_eval.py

Optional:
  CONCORD_FIXTURE_ROOT=/path/to/tasklab
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

# Add src to path when run as script
_CODE_ROOT = Path(__file__).resolve().parent.parent
if str(_CODE_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_CODE_ROOT / "src"))

from concordcoder.llm_client import get_llm_client  # noqa: E402
from concordcoder.pipeline import run_single_task  # noqa: E402
from concordcoder.schemas import OutputFormat, SingleTaskSpec  # noqa: E402
from concordcoder.single_task import load_task_spec  # noqa: E402


def _pytest_summary(repo: Path) -> dict:
    tests = repo / "tests"
    if not tests.is_dir():
        return {"ran": False, "exit_code": None, "pass": None}
    r = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", str(tests)],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    return {
        "ran": True,
        "exit_code": r.returncode,
        "pass": r.returncode == 0,
    }


def main() -> None:
    default_repo = _CODE_ROOT / "fixtures" / "repos" / "tasklab"
    repo = Path(os.environ.get("CONCORD_FIXTURE_ROOT", default_repo)).resolve()
    task_dir = _CODE_ROOT / "fixtures" / "tasks"

    rows: list[dict] = []
    yamls = sorted(task_dir.glob("*.yaml"))
    if not yamls:
        print(json.dumps({"error": "no task yaml", "task_dir": str(task_dir)}))
        sys.exit(1)

    pyt = _pytest_summary(repo)

    try:
        llm = get_llm_client()
    except EnvironmentError as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)

    variants = [
        ("narrow_no_anchor", False, False),
        ("with_anchor", True, False),
        ("anchor_with_probe", True, True),
    ]

    for ypath in yamls:
        ft = load_task_spec(ypath)
        for vname, use_a, with_p in variants:
            spec = SingleTaskSpec(
                task_id=ft.id,
                task=ft.task,
                target_file=ft.target_file,
                target_symbol=ft.target_symbol,
                use_anchor=use_a,
                with_probe=with_p,
                full_align=False,
                output_format=OutputFormat.MARKDOWN_PLAN,
                answers=ft.alignment_answers,
            )
            st = run_single_task(repo, spec, llm_client=llm, fast_extract=True)
            rows.append(
                {
                    "task_id": ft.id,
                    "task_yaml": ypath.name,
                    "variant": vname,
                    "dependency_level": ft.dependency_level.value,
                    "use_anchor": use_a,
                    "with_probe": with_p,
                    "pytest": pyt,
                    "warnings_n": len(st.generation.warnings),
                    "code_plan_len": len(st.generation.code_plan or ""),
                    "probe": st.probe,
                    "n_parsed_files": len(st.parsed_files),
                }
            )

    out = {
        "fixture_repo": str(repo),
        "rows": rows,
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
