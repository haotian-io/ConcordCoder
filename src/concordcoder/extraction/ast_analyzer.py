"""AST-based static analyzer: extract functions, classes, imports from Python files."""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class FunctionInfo:
    name: str
    qualname: str          # e.g. "MyClass.my_method"
    path: str
    start_line: int
    end_line: int
    args: list[str] = field(default_factory=list)
    decorators: list[str] = field(default_factory=list)
    docstring: str = ""
    is_public: bool = True


@dataclass
class ClassInfo:
    name: str
    path: str
    start_line: int
    end_line: int
    bases: list[str] = field(default_factory=list)
    methods: list[str] = field(default_factory=list)
    docstring: str = ""


@dataclass
class ImportInfo:
    module: str
    names: list[str]
    is_from: bool
    path: str


@dataclass
class FileAnalysis:
    path: str
    functions: list[FunctionInfo] = field(default_factory=list)
    classes: list[ClassInfo] = field(default_factory=list)
    imports: list[ImportInfo] = field(default_factory=list)
    todos: list[str] = field(default_factory=list)
    parse_error: str | None = None


class ASTAnalyzer:
    """Parse Python files and extract structural information via AST."""

    def analyze_file(self, path: Path) -> FileAnalysis:
        result = FileAnalysis(path=str(path))
        try:
            source = path.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(source, filename=str(path))
        except SyntaxError as e:
            result.parse_error = str(e)
            return result
        except OSError as e:
            result.parse_error = str(e)
            return result

        # Extract TODO/FIXME/HACK comments
        for line in source.splitlines():
            stripped = line.strip()
            for tag in ("TODO", "FIXME", "HACK", "NOTE", "XXX"):
                if tag in stripped:
                    result.todos.append(stripped)
                    break

        visitor = _StructureVisitor(str(path))
        visitor.visit(tree)

        result.functions = visitor.functions
        result.classes = visitor.classes
        result.imports = visitor.imports
        return result

    def analyze_repo(self, repo_root: Path, max_files: int = 120) -> dict[str, FileAnalysis]:
        """Analyze all Python files in repo. Returns path → FileAnalysis map."""
        skip = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build", ".pytest_cache"}
        analyses: dict[str, FileAnalysis] = {}

        for fpath in sorted(repo_root.rglob("*.py")):
            rel = fpath.relative_to(repo_root)
            if any(p in skip for p in rel.parts):
                continue
            if len(analyses) >= max_files:
                break
            analyses[str(rel)] = self.analyze_file(fpath)

        return analyses


class _StructureVisitor(ast.NodeVisitor):
    def __init__(self, filepath: str) -> None:
        self.filepath = filepath
        self.functions: list[FunctionInfo] = []
        self.classes: list[ClassInfo] = []
        self.imports: list[ImportInfo] = []
        self._class_stack: list[str] = []

    def visit_Import(self, node: ast.Import) -> None:
        self.imports.append(
            ImportInfo(
                module="",
                names=[alias.name for alias in node.names],
                is_from=False,
                path=self.filepath,
            )
        )
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        self.imports.append(
            ImportInfo(
                module=node.module or "",
                names=[alias.name for alias in node.names],
                is_from=True,
                path=self.filepath,
            )
        )
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        bases = [ast.unparse(b) for b in node.bases]
        methods = [
            n.name
            for n in ast.walk(node)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        docstring = ast.get_docstring(node) or ""
        self.classes.append(
            ClassInfo(
                name=node.name,
                path=self.filepath,
                start_line=node.lineno,
                end_line=node.end_lineno or node.lineno,
                bases=bases,
                methods=methods,
                docstring=docstring[:300],
            )
        )
        self._class_stack.append(node.name)
        self.generic_visit(node)
        self._class_stack.pop()

    def _visit_func(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        qualname = ".".join(self._class_stack + [node.name])
        args = [arg.arg for arg in node.args.args]
        decorators = [ast.unparse(d) for d in node.decorator_list]
        docstring = ast.get_docstring(node) or ""
        self.functions.append(
            FunctionInfo(
                name=node.name,
                qualname=qualname,
                path=self.filepath,
                start_line=node.lineno,
                end_line=node.end_lineno or node.lineno,
                args=args,
                decorators=decorators,
                docstring=docstring[:300],
                is_public=not node.name.startswith("_"),
            )
        )
        # Don't push class stack for nested functions
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_func(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_func(node)
