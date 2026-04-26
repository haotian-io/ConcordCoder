#!/usr/bin/env python3
"""
Mini evaluation: user-supplied **real** repo × task YAMLs × baseline variants → JSON on stdout.

Requires the same API keys as ``concord once`` (OPENAI_API_KEY and optional OPENAI_BASE_URL).
Each row uses ``full_align=True`` (LLM batch alignment), matching ``concord once`` defaults.

**No bundled sample repository.** Set:

- ``CONCORD_EVAL_REPO_ROOT`` — absolute path to the repository root to evaluate.
- **One of:** ``CONCORD_EVAL_TASKS_DIR`` (directory of ``*.yaml``) or ``CONCORD_EVAL_TASKS_GLOB``
  (shell glob, e.g. ``/path/to/tasks/*.yaml``).

If either is missing, prints a JSON error object and exits with code 1.

Output shape (artifact / regression):
  Top level: ``eval_repo``, ``rows`` (``fixture_repo`` is also set to the same string for older parsers)
  Each row: task_id, task_yaml, variant (narrow_no_anchor | with_anchor |
            anchor_with_probe), dependency_level, use_anchor, with_probe,
            pytest{ran, exit_code, pass}, warnings_n, code_plan_len, probe, n_parsed_files

Example::

  export CONCORD_EVAL_REPO_ROOT=/path/to/your/clone
  export CONCORD_EVAL_TASKS_DIR=/path/to/dir/with/yamls
  python3 scripts/mini_eval.py
"""

from __future__ import annotations

import glob as glob_module
import json
import os
import subprocess
import sys
from pathlib import Path

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


def _collect_yaml_paths() -> tuple[list[Path] | None, str | None]:
    """Return (yaml_paths, error_message)."""
    g = os.environ.get("CONCORD_EVAL_TASKS_GLOB", "").strip()
    d = os.environ.get("CONCORD_EVAL_TASKS_DIR", "").strip()
    if not g and not d:
        return None, "Set CONCORD_EVAL_TASKS_GLOB or CONCORD_EVAL_TASKS_DIR"
    if g and d:
        return None, "Set only one of CONCORD_EVAL_TASKS_GLOB or CONCORD_EVAL_TASKS_DIR"
    if g:
        paths = [Path(p).resolve() for p in sorted(glob_module.glob(g))]
        paths = [p for p in paths if p.is_file() and p.suffix.lower() in (".yaml", ".yml")]
        return (paths if paths else None), None if paths else f"No YAML files matched: {g!r}"
    if d:
        base = Path(d).resolve()
        if not base.is_dir():
            return None, f"CONCORD_EVAL_TASKS_DIR is not a directory: {base}"
        paths = sorted(base.glob("*.yaml")) + sorted(base.glob("*.yml"))
        seen: set[Path] = set()
        uniq: list[Path] = []
        for p in paths:
            if p not in seen:
                seen.add(p)
                uniq.append(p)
        if not uniq:
            return None, f"No *.yaml or *.yml in {base}"
        return uniq, None


def main() -> None:
    repo_raw = os.environ.get("CONCORD_EVAL_REPO_ROOT", "").strip()
    if not repo_raw:
        print(
            json.dumps(
                {
                    "error": "CONCORD_EVAL_REPO_ROOT is required (path to a real repository).",
                    "required_env": [
                        "CONCORD_EVAL_REPO_ROOT",
                        "CONCORD_EVAL_TASKS_DIR or CONCORD_EVAL_TASKS_GLOB",
                    ],
                },
                ensure_ascii=False,
            )
        )
        sys.exit(1)

    repo = Path(repo_raw).resolve()
    if not repo.is_dir():
        print(json.dumps({"error": f"CONCORD_EVAL_REPO_ROOT is not a directory: {repo}"}))
        sys.exit(1)

    yamls, yerr = _collect_yaml_paths()
    if yerr or not yamls:
        print(
            json.dumps(
                {
                    "error": yerr or "No task YAML files found.",
                    "required_env": [
                        "CONCORD_EVAL_REPO_ROOT",
                        "CONCORD_EVAL_TASKS_DIR or CONCORD_EVAL_TASKS_GLOB",
                    ],
                },
                ensure_ascii=False,
            )
        )
        sys.exit(1)

    rows: list[dict] = []
    pyt = _pytest_summary(repo)
    fairness_budget = {
        "max_turns": int(os.environ.get("CONCORD_FAIR_MAX_TURNS", "3")),
        "max_prompt_tokens": int(os.environ.get("CONCORD_FAIR_MAX_PROMPT_TOKENS", "4000")),
        "max_completion_tokens": int(os.environ.get("CONCORD_FAIR_MAX_COMPLETION_TOKENS", "4000")),
        "max_wallclock_sec": int(os.environ.get("CONCORD_FAIR_MAX_WALLCLOCK_SEC", "300")),
    }

    try:
        llm = get_llm_client()
    except EnvironmentError as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False), file=sys.stderr)
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
                full_align=True,
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
                    "fairness_budget": fairness_budget,
                    "alignment_turn_log_n": len(st.alignment_turn_log),
                    "artifact_quality_score": st.artifact_quality_score,
                    "user_confidence_score": st.user_confidence_score,
                    "cost": st.cost.model_dump(mode="json"),
                }
            )

    repo_s = str(repo)
    out = {
        "eval_repo": repo_s,
        "fixture_repo": repo_s,
        "rows": rows,
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
