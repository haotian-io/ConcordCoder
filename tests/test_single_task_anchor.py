"""run_single_task with use_anchor and with_probe on a minimal temp repo."""

from __future__ import annotations

from pathlib import Path

from concordcoder.pipeline import run_single_task
from concordcoder.schemas import OutputFormat, SingleTaskSpec
from tests.conftest import StubLLM


def _write_minimal_repo(root: Path) -> None:
    pkg = root / "demo_pkg"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "vowels.py").write_text(
        '''"""Tiny package for anchor tests."""
import re


def count_vowels(s: str) -> int:
    """Return the number of vowels (aeiou, case-insensitive) in s."""
    # CONCORD_TASK_BEGIN
    return 0
    # CONCORD_TASK_END
''',
        encoding="utf-8",
    )
    tests = root / "tests"
    tests.mkdir(parents=True)
    (tests / "test_vowels.py").write_text(
        '''from demo_pkg.vowels import count_vowels


def test_count_vowels():
    assert count_vowels("hello") == 2
''',
        encoding="utf-8",
    )
    (root / "pyproject.toml").write_text(
        '[project]\nname = "demo-pkg-eval"\nversion = "0.0.1"\n',
        encoding="utf-8",
    )


def test_run_single_task_with_anchor_fills_assembly(tmp_path: Path) -> None:
    _write_minimal_repo(tmp_path)
    spec = SingleTaskSpec(
        task="Implement count_vowels.",
        target_file="demo_pkg/vowels.py",
        target_symbol="count_vowels",
        use_anchor=True,
        with_probe=True,
        output_format=OutputFormat.MARKDOWN_PLAN,
    )
    st = run_single_task(
        tmp_path,
        spec,
        llm_client=StubLLM(),
        fast_extract=True,
    )
    assert st.probe.get("n_probes") is not None
    assert st.generation.code_plan
