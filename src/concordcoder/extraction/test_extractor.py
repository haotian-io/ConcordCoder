"""Test file extractor: infer constraints and behavior expectations from test files."""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class TestExpectation:
    test_file: str
    test_name: str
    description: str           # Human-readable inferred constraint
    target_symbol: str = ""    # The function/class being tested


@dataclass
class TestAnalysis:
    expectations: list[TestExpectation] = field(default_factory=list)
    fixture_names: list[str] = field(default_factory=list)
    tested_symbols: list[str] = field(default_factory=list)
    test_files: list[str] = field(default_factory=list)


# Patterns that indicate constraint-like expectations in test code
_ASSERT_PATTERNS = [
    (r"assert.*raises\s*\((\w+)", "raises {0} on invalid input"),
    (r"assert.*not.*None", "result must not be None"),
    (r"assert.*==\s*['\"]([^'\"]+)['\"]", "return value must equal '{0}'"),
    (r"mock.*called_once", "must be called exactly once"),
    (r"mock.*not.*called", "must NOT be called"),
]
_COMPILED_PATTERNS = [(re.compile(p, re.IGNORECASE), tmpl) for p, tmpl in _ASSERT_PATTERNS]


class TestExtractor:
    """Analyze test files to extract implicit behavior constraints."""

    def analyze_repo(self, repo_root: Path) -> TestAnalysis:
        skip = {".git", ".venv", "venv", "__pycache__", "dist", "build"}
        test_files = []

        for path in sorted(repo_root.rglob("*.py")):
            rel = path.relative_to(repo_root)
            if any(p in skip for p in rel.parts):
                continue
            name = path.name
            if name.startswith("test_") or name.endswith("_test.py") or "test" in rel.parts:
                test_files.append(path)

        analysis = TestAnalysis()
        for tf in test_files:
            rel_str = str(tf.relative_to(repo_root))
            analysis.test_files.append(rel_str)
            self._analyze_file(tf, rel_str, analysis)

        return analysis

    def _analyze_file(self, path: Path, rel_str: str, analysis: TestAnalysis) -> None:
        try:
            source = path.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(source, filename=str(path))
        except (SyntaxError, OSError):
            return

        visitor = _TestVisitor(rel_str)
        visitor.visit(tree)

        analysis.fixture_names.extend(visitor.fixture_names)
        analysis.tested_symbols.extend(visitor.tested_symbols)

        for test_name, body_lines in visitor.test_bodies:
            for line in body_lines:
                for pattern, template in _COMPILED_PATTERNS:
                    m = pattern.search(line)
                    if m:
                        groups = m.groups()
                        desc = template.format(*groups) if groups else template
                        analysis.expectations.append(
                            TestExpectation(
                                test_file=rel_str,
                                test_name=test_name,
                                description=desc,
                            )
                        )
                        break


class _TestVisitor(ast.NodeVisitor):
    def __init__(self, filepath: str) -> None:
        self.filepath = filepath
        self.fixture_names: list[str] = []
        self.tested_symbols: list[str] = []
        self.test_bodies: list[tuple[str, list[str]]] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        # Collect pytest fixtures
        for dec in node.decorator_list:
            if isinstance(dec, ast.Attribute) and dec.attr == "fixture":
                self.fixture_names.append(node.name)
            elif isinstance(dec, ast.Name) and dec.id == "fixture":
                self.fixture_names.append(node.name)

        # Collect test functions
        if node.name.startswith("test_"):
            # Extract source lines for pattern matching
            body_src: list[str] = []
            for child in ast.walk(node):
                if isinstance(child, ast.Expr) and isinstance(child.value, ast.Call):
                    body_src.append(ast.unparse(child.value))
                if isinstance(child, ast.Assert):
                    body_src.append(ast.unparse(child))
                if isinstance(child, ast.Name):
                    self.tested_symbols.append(child.id)
            self.test_bodies.append((node.name, body_src))

        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        # Reuse sync handler
        sync_node = ast.FunctionDef(
            name=node.name,
            args=node.args,
            body=node.body,
            decorator_list=node.decorator_list,
            returns=node.returns,
        )
        ast.copy_location(sync_node, node)
        self.visit_FunctionDef(sync_node)
