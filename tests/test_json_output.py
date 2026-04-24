"""json_files / unified_diff parsing and ConstrainedGenerator with mock LLM."""

from __future__ import annotations

import json
from pathlib import Path

from concordcoder.generation.constrained_gen import ConstrainedGenerator
from concordcoder.generation.json_output import parse_json_generation_response, parse_unified_diff_response
from concordcoder.pipeline import run_single_task, write_single_task_artifacts
from concordcoder.schemas import (
    OutputFormat,
    SingleTaskSpec,
)


def test_parse_json_generation_response_ok() -> None:
    raw = """
```json
{
  "files": [{"path": "a/b.py", "content": "x = 1\\n"}],
  "cognitive_summary": "test"
}
```
"""
    files, summ, w = parse_json_generation_response(raw)
    assert not w
    assert summ == "test"
    assert len(files) == 1
    assert files[0].path == "a/b.py"
    assert "x = 1" in files[0].content


def test_parse_unified_diff_response_fence() -> None:
    t = """```diff
--- a/f.py
+++ b/f.py
@@
-x
+y
```"""
    d = parse_unified_diff_response(t)
    assert "+++ b/f.py" in d


def test_constrained_gen_json_mode_mock_llm() -> None:
    class MockLLM:
        def chat(self, messages, system: str = "") -> str:  # noqa: ARG002
            return (
                '{"files": [{"path": "x.py", "content": "print(1)"}], '
                '"cognitive_summary": "ok"}'
            )

    from concordcoder.alignment.dialogue import AlignmentDialogue
    from concordcoder.schemas import ContextBundle, GenerationRequest

    bundle = ContextBundle(task_summary="t")
    alignment = AlignmentDialogue().draft_record(bundle, None)
    req = GenerationRequest(
        repo_root=".",
        user_request="add file",
        bundle=bundle,
        alignment=alignment,
        output_format=OutputFormat.JSON_FILES,
    )
    gen = ConstrainedGenerator(llm_client=MockLLM())
    r = gen.generate(req)
    assert r.structured_files
    assert r.structured_files[0].path == "x.py"
    assert "print(1)" in r.structured_files[0].content


def test_run_single_task_fast_no_llm(tmp_path: Path) -> None:
    (tmp_path / "hi.py").write_text("a = 1\n", encoding="utf-8")
    spec = SingleTaskSpec(
        task="change nothing",
        full_align=False,
        output_format=OutputFormat.MARKDOWN_PLAN,
    )
    st = run_single_task(tmp_path, spec, llm_client=None, fast_extract=True)
    assert st.generation.warnings
    out = write_single_task_artifacts(st, tmp_path / "out")
    assert (out / "result.json").is_file()
    row = json.loads((out / "result.json").read_text(encoding="utf-8"))
    assert row["generation"]["warnings"]
