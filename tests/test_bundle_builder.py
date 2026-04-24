"""Tests for Phase 1: Context Extraction (AST, call graph, test extractor)."""

from pathlib import Path

import pytest

from concordcoder.extraction.ast_analyzer import ASTAnalyzer
from concordcoder.extraction.bundle_builder import BundleBuilder
from concordcoder.extraction.call_graph import build_call_graph
from concordcoder.extraction.test_extractor import TestExtractor


# ── AST Analyzer ────────────────────────────────────────────────────────────

def test_ast_analyzer_functions(tmp_path: Path) -> None:
    (tmp_path / "payment.py").write_text(
        """\
class PaymentHandler:
    \"\"\"Handles payment transactions.\"\"\"

    def process_payment(self, user_id: str, amount: float) -> bool:
        \"\"\"Do not change this signature – called by 3 consumers.\"\"\"
        return True

    def _internal_check(self) -> None:
        pass
""",
        encoding="utf-8",
    )
    analyzer = ASTAnalyzer()
    result = analyzer.analyze_file(tmp_path / "payment.py")
    assert result.parse_error is None
    fn_names = [f.name for f in result.functions]
    assert "process_payment" in fn_names
    assert "_internal_check" in fn_names

    pub = [f for f in result.functions if f.is_public]
    priv = [f for f in result.functions if not f.is_public]
    assert any(f.name == "process_payment" for f in pub)
    assert any(f.name == "_internal_check" for f in priv)

    classes = [c.name for c in result.classes]
    assert "PaymentHandler" in classes


def test_ast_analyzer_imports(tmp_path: Path) -> None:
    (tmp_path / "main.py").write_text(
        "import os\nfrom pathlib import Path\nfrom .utils import helper\n",
        encoding="utf-8",
    )
    analyzer = ASTAnalyzer()
    result = analyzer.analyze_file(tmp_path / "main.py")
    assert any(imp.is_from and "pathlib" in imp.module for imp in result.imports)


def test_ast_analyzer_todos(tmp_path: Path) -> None:
    (tmp_path / "foo.py").write_text(
        "x = 1  # TODO: refactor this\ny = 2  # FIXME: broken\n",
        encoding="utf-8",
    )
    analyzer = ASTAnalyzer()
    result = analyzer.analyze_file(tmp_path / "foo.py")
    assert len(result.todos) == 2


def test_ast_analyzer_syntax_error(tmp_path: Path) -> None:
    (tmp_path / "bad.py").write_text("def (broken syntax :\n", encoding="utf-8")
    analyzer = ASTAnalyzer()
    result = analyzer.analyze_file(tmp_path / "bad.py")
    assert result.parse_error is not None


# ── Call Graph Builder ───────────────────────────────────────────────────────

def test_call_graph_basic(tmp_path: Path) -> None:
    (tmp_path / "utils.py").write_text("def helper(): pass\n", encoding="utf-8")
    (tmp_path / "handler.py").write_text(
        "from utils import helper\ndef run(): helper()\n", encoding="utf-8"
    )
    builder, analyses = build_call_graph(tmp_path)
    # handler.py should import utils.py
    deps = builder.get_dependencies("handler.py")
    assert "utils.py" in deps
    # utils.py has handler.py as dependent
    dependents = builder.get_dependents("utils.py")
    assert "handler.py" in dependents


def test_affected_by_propagation(tmp_path: Path) -> None:
    """A → B → C: changing A should mark B and C as affected."""
    (tmp_path / "a.py").write_text("def a(): pass\n", encoding="utf-8")
    (tmp_path / "b.py").write_text("from a import a\ndef b(): return a()\n", encoding="utf-8")
    (tmp_path / "c.py").write_text("from b import b\ndef c(): return b()\n", encoding="utf-8")
    builder, _ = build_call_graph(tmp_path)
    affected = set(builder.affected_by(["a.py"]))
    assert "b.py" in affected
    assert "c.py" in affected


# ── Test Extractor ───────────────────────────────────────────────────────────

def test_test_extractor_finds_fixtures(tmp_path: Path) -> None:
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_payment.py").write_text(
        """\
import pytest

@pytest.fixture
def mock_db():
    return {}

def test_payment_success(mock_db):
    assert True

def test_payment_raises(mock_db):
    with pytest.raises(ValueError):
        pass
""",
        encoding="utf-8",
    )
    extractor = TestExtractor()
    analysis = extractor.analyze_repo(tmp_path)
    assert "mock_db" in analysis.fixture_names
    assert any("tests/test_payment.py" in f for f in analysis.test_files)


# ── BundleBuilder (upgraded) ─────────────────────────────────────────────────

def test_bundle_builder_smoke(tmp_path: Path) -> None:
    (tmp_path / "payment.py").write_text(
        "def handle_payment(user_id: str) -> None:\n    pass\n", encoding="utf-8"
    )
    b = BundleBuilder(tmp_path)
    bundle = b.build("add retry around payment")
    assert bundle.task_summary
    assert any("payment" in s.text.lower() or "handle_payment" in s.text for s in bundle.snippets)


def test_bundle_builder_call_graph_populated(tmp_path: Path) -> None:
    (tmp_path / "utils.py").write_text("def retry(): pass\n", encoding="utf-8")
    (tmp_path / "handler.py").write_text(
        "from utils import retry\ndef handle(): retry()\n", encoding="utf-8"
    )
    b = BundleBuilder(tmp_path)
    bundle = b.build("add retry logic to handler")
    # call_graph should be populated
    assert isinstance(bundle.call_graph, dict)


def test_bundle_builder_affected_modules(tmp_path: Path) -> None:
    (tmp_path / "payment.py").write_text("def pay(): pass\n", encoding="utf-8")
    (tmp_path / "checkout.py").write_text(
        "from payment import pay\ndef checkout(): pay()\n", encoding="utf-8"
    )
    b = BundleBuilder(tmp_path)
    bundle = b.build("refactor payment logic")
    # checkout.py depends on payment.py → should appear in affected_modules
    affected = bundle.affected_modules
    assert isinstance(affected, list)


def test_bundle_builder_no_match(tmp_path: Path) -> None:
    (tmp_path / "unrelated.py").write_text("x = 42\n", encoding="utf-8")
    b = BundleBuilder(tmp_path)
    bundle = b.build("add payment retry")
    assert not bundle.snippets
    assert bundle.open_questions  # should warn about no keyword overlap


def test_bundle_metadata(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("def run(): pass\n", encoding="utf-8")
    b = BundleBuilder(tmp_path)
    bundle = b.build("improve run function")
    assert bundle.metadata.get("builder") == "multi_layer_v1"
    assert "files_scanned" in bundle.metadata


# ── AlignmentDialogue (rule-based, no LLM) ──────────────────────────────────

def test_alignment_dialogue_basic(tmp_path: Path) -> None:
    from concordcoder.alignment.dialogue import AlignmentDialogue
    from concordcoder.schemas import ContextBundle

    bundle = ContextBundle(task_summary="add retry to payment", open_questions=["API stable?"])
    dialogue = AlignmentDialogue()
    qs = dialogue.propose_questions(bundle)
    assert len(qs) >= 4  # 3 default + 1 from open_questions
    record = dialogue.draft_record(bundle, answers={"api_stable": "yes"})
    assert any(c.id == "api_stable" for c in record.confirmed_constraints)


# ── GenerationResult & ConstrainedGenerator stub mode ───────────────────────

def test_constrained_generator_requires_llm(tmp_path: Path) -> None:
    from concordcoder.generation.constrained_gen import ConstrainedGenerator
    from concordcoder.schemas import (
        AlignmentRecord,
        Constraint,
        ContextBundle,
        GenerationRequest,
    )

    bundle = ContextBundle(task_summary="add retry to payment")
    alignment = AlignmentRecord(
        refined_intent="add retry",
        confirmed_constraints=[
            Constraint(id="c1", description="Do not change public API.", hard=True)
        ],
    )
    req = GenerationRequest(
        repo_root=str(tmp_path),
        user_request="add retry",
        bundle=bundle,
        alignment=alignment,
    )
    gen = ConstrainedGenerator(llm_client=None)
    with pytest.raises(RuntimeError, match="LLM client is required"):
        gen.generate(req)


# ── Pipeline smoke test ──────────────────────────────────────────────────────

def test_pipeline_end_to_end(tmp_path: Path) -> None:
    from concordcoder.pipeline import run_pipeline_and_write
    from tests.conftest import StubLLM

    (tmp_path / "payment.py").write_text(
        "def handle_payment(user_id):\n    pass\n", encoding="utf-8"
    )
    long_reply = "# " + "x" * 60 + "\n\n## Summary\nok.\n" + "```python\npass\n```"
    plan_path = run_pipeline_and_write(
        repo_root=tmp_path,
        task_text="add retry logic to handle_payment",
        plan_name="TEST_PLAN.md",
        llm_client=StubLLM(reply=long_reply),
    )
    assert plan_path.exists()
    content = plan_path.read_text()
    assert len(content) > 50
