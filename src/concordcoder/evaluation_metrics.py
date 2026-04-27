"""
RQ1 Enhanced Evaluation Metrics Module

Comprehensive metrics for code generation quality assessment:
- File Hit Rate (FHR)
- Diff Generation Rate (DGR)
- Pass@1 (Test Pass Rate)
- Constraint Violation Rate (CVR)
- Regression Rate (RR)
- Edit Distance to Ground Truth (ED)
- AST Similarity (AST-SIM)
- CodeBLEU Score
- Code Complexity Metrics
"""

from __future__ import annotations

import ast
import difflib
import re
import subprocess
from pathlib import Path
from typing import Any

try:
    from swebench.harness.run_evaluation import get_instances
    from swebench.harness.constants import SWEbenchInstance
    HAS_SWEBENCH = True
except ImportError:
    HAS_SWEBENCH = False


def _norm_relpath(p: str) -> str:
    """Normalize ``a/foo``, ``b/foo`` → ``foo`` for SWE file matching."""
    p = (p or "").replace("\\", "/").strip()
    if p in ("/dev/null", "dev/null"):
        return ""
    for prefix in ("a/", "b/"):
        if p.startswith(prefix) and len(p) > 2 and p[2:3] not in ("/",):
            p = p[2:]
    return p.lstrip("./")


def _all_paths_from_patch(patch: str) -> list[str]:
    """Extract all file paths from a unified diff patch."""
    paths = []
    for line in (patch or "").splitlines():
        m = re.match(r"^\+\+\+\s+b/(\S+)", line)
        if m:
            paths.append(m.group(1))
    return list(dict.fromkeys(paths))


def _first_path_from_patch(patch: str) -> str | None:
    """Extract first file path from a unified diff patch."""
    if not patch:
        return None
    for line in patch.splitlines():
        m = re.match(r"^---\s+a/(\S+)", line)
        if m:
            return m.group(1)
    return None


def _predicted_paths_from_task(st) -> list[str]:
    """Extract predicted file paths from task result."""
    from concordcoder.generation.json_output import paths_from_unified_diff

    out: list[str] = []
    for f in st.parsed_files or []:
        if getattr(f, "path", ""):
            out.append(f.path)
    out.extend(st.generation.changed_files or [])
    u = (st.unified_diff or st.generation.unified_diff_text or "").strip()
    if u:
        out.extend(paths_from_unified_diff(u))
    raw = (st.generation.code_plan or "").strip()
    if not out and raw:
        out.extend(paths_from_unified_diff(raw))
    return list(dict.fromkeys([p for p in out if p]))[:50]


class EvaluationMetrics:
    """Comprehensive evaluation metrics for code generation quality."""

    def __init__(self, instance: dict, result: dict, repo_root: Path | None = None):
        self.instance = instance
        self.result = result
        self.repo_root = repo_root
        self.gold_patch = instance.get("patch", "")
        self.gold_test_patch = instance.get("test_patch", "")
        self.instance_id = instance.get("instance_id", "")
        self.repo = instance.get("repo", "")

    @property
    def gold_files(self) -> list[str]:
        """Ground truth modified files."""
        return _all_paths_from_patch(self.gold_patch)

    @property
    def gold_first_file(self) -> str | None:
        """First ground truth modified file."""
        return _first_path_from_patch(self.gold_patch)

    @property
    def predicted_files(self) -> list[str]:
        """Predicted modified files from generation result."""
        if isinstance(self.result, dict):
            pf = self.result.get("predicted_files", [])
            if pf:
                return pf
        return []

    def file_hit_rate(self) -> float:
        """File Hit Rate (FHR): Fraction of gold files correctly predicted."""
        gs = {_norm_relpath(x) for x in self.gold_files if _norm_relpath(x)}
        if not gs:
            return 0.0
        pred_set = {_norm_relpath(p) for p in self.predicted_files if _norm_relpath(p)}
        hit = len(gs & pred_set)
        return hit / len(gs)

    def diff_generation_rate(self) -> float:
        """Diff Generation Rate (DGR): Whether any diff was generated."""
        if isinstance(self.result, dict):
            diff_len = self.result.get("unified_diff_len", 0)
            return 1.0 if diff_len > 0 else 0.0
        return 0.0

    def constraint_violation_rate(self) -> float:
        """Constraint Violation Rate (CVR): Fraction of violated hard constraints."""
        if isinstance(self.result, dict):
            compliance = self.result.get("constraint_compliance", {})
            if not compliance:
                return 0.0
            violated = sum(1 for v in compliance.values() if not v)
            return violated / len(compliance)
        return 0.0

    def regression_rate(self) -> float:
        """
        Regression Rate (RR): Whether the patch causes original passing tests to fail.

        This requires applying the patch and running tests, which is expensive.
        Returns -1.0 if not computed (harness not available).
        """
        if not HAS_SWEBENCH or self.repo_root is None:
            return -1.0
        # This would need the full SWE-bench harness to compute
        # Placeholder for now - actual implementation requires Docker
        return -1.0

    def edit_distance(self) -> dict[str, float]:
        """
        Edit Distance to Ground Truth (ED).

        Returns:
            dict with 'levenshtein': normalized Levenshtein distance (0=identical, 1=completely different)
        """
        if not self.gold_patch or not self.result.get("unified_diff_text"):
            return {"levenshtein": 1.0, "normalized": 1.0}

        gold_diff = self.gold_patch.strip()
        pred_diff = self.result.get("unified_diff_text", "").strip()

        if not gold_diff or not pred_diff:
            return {"levenshtein": 1.0, "normalized": 1.0}

        # Normalized Levenshtein distance
        gold_lines = gold_diff.splitlines(keepends=True)
        pred_lines = pred_diff.splitlines(keepends=True)

        matcher = difflib.SequenceMatcher(None, gold_lines, pred_lines)
        distance = 1.0 - matcher.ratio()  # 0=identical, 1=completely different

        # Character-level Levenshtein
        import Levenshtein
        lev_dist = Levenshtein.distance(gold_diff, pred_diff)
        max_len = max(len(gold_diff), len(pred_diff), 1)
        norm_lev = lev_dist / max_len

        return {
            "levenshtein": norm_lev,
            "sequence_ratio": matcher.ratio(),
            "normalized": distance
        }

    def ast_similarity(self) -> dict[str, Any]:
        """
        AST Similarity (AST-SIM): Structural similarity between generated and gold code.

        For each changed file, compare AST structure.
        """
        if not self.gold_patch or not self.result.get("unified_diff_text"):
            return {"mean_similarity": 0.0, "per_file": {}}

        gold_files = self.gold_files
        pred_files = self.predicted_files

        per_file_scores = {}
        common_files = set(gold_files) & set(pred_files)

        for fpath in common_files:
            gold_content = self._extract_file_from_patch(self.gold_patch, fpath)
            pred_content = self._extract_content_for_file(fpath)

            if gold_content and pred_content:
                sim = self._ast_similarity(gold_content, pred_content)
                per_file_scores[fpath] = sim

        if not per_file_scores:
            return {"mean_similarity": 0.0, "per_file": {}}

        mean_sim = sum(per_file_scores.values()) / len(per_file_scores)
        return {"mean_similarity": mean_sim, "per_file": per_file_scores}

    def _extract_file_from_patch(self, patch: str, target_file: str) -> str | None:
        """Extract file content from a unified diff patch."""
        lines = patch.splitlines()
        content_lines = []
        in_target = False

        for i, line in enumerate(lines):
            if re.match(r"^\+\+\+ b/" + re.escape(target_file) + r"$", line):
                in_target = True
                continue
            if in_target:
                if line.startswith("diff --git") or re.match(r"^\+\+\+ b/", line):
                    break
                if line.startswith("+") and not line.startswith("+++"):
                    content_lines.append(line[1:])
                elif line.startswith(" ") or line.startswith("-"):
                    content_lines.append(line[1:])

        return "\n".join(content_lines) if content_lines else None

    def _extract_content_for_file(self, fpath: str) -> str | None:
        """Extract predicted content for a file from result."""
        if isinstance(self.result, dict):
            for pf in self.result.get("parsed_files", []):
                if pf.get("path") == fpath:
                    return pf.get("content", "")
        return None

    def _ast_similarity(self, code1: str, code2: str) -> float:
        """Calculate AST structural similarity between two code snippets."""
        try:
            tree1 = ast.parse(code1)
            tree2 = ast.parse(code2)
        except SyntaxError:
            return 0.0

        struct1 = self._ast_to_structure(tree1)
        struct2 = self._ast_to_structure(tree2)

        matcher = difflib.SequenceMatcher(None, struct1, struct2)
        return matcher.ratio()

    def _ast_to_structure(self, tree: ast.AST) -> list[str]:
        """Convert AST to a list of node types for structural comparison."""
        nodes = []
        for node in ast.walk(tree):
            nodes.append(type(node).__name__)
        return nodes

    def codebleu_score(self) -> dict[str, float]:
        """
        CodeBLEU Score approximation.

        CodeBLEU = weighted_sum(alpha * n-gram_match + beta * weighted_ngram_match
                                 + gamma * AST_match + delta * data_flow_match)

        This is a simplified approximation. Full CodeBLEU requires the code_transitor package.
        """
        if not self.gold_patch or not self.result.get("unified_diff_text"):
            return {"codebleu_approx": 0.0}

        gold_files = self.gold_files
        pred_files = self.predicted_files

        total_score = 0.0
        n_common = 0

        for gf in gold_files:
            if gf in pred_files:
                gold_content = self._extract_file_from_patch(self.gold_patch, gf)
                pred_content = self._extract_content_for_file(gf)

                if gold_content and pred_content:
                    # Simplified BLEU-like score using n-gram overlap
                    score = self._ngram_overlap(gold_content, pred_content)
                    total_score += score
                    n_common += 1

        if n_common == 0:
            return {"codebleu_approx": 0.0}

        return {"codebleu_approx": total_score / n_common}

    def _ngram_overlap(self, ref: str, hyp: str, n: int = 4) -> float:
        """Calculate n-gram overlap between reference and hypothesis."""
        ref_tokens = ref.split()
        hyp_tokens = hyp.split()

        if not ref_tokens or not hyp_tokens:
            return 0.0

        ref_ngrams = set()
        for i in range(len(ref_tokens) - n + 1):
            ref_ngrams.add(tuple(ref_tokens[i:i+n]))

        hyp_ngrams = set()
        for i in range(len(hyp_tokens) - n + 1):
            hyp_ngrams.add(tuple(hyp_tokens[i:i+n]))

        if not ref_ngrams:
            return 0.0

        overlap = len(ref_ngrams & hyp_ngrams)
        return overlap / len(ref_ngrams)

    def code_complexity_metrics(self) -> dict[str, Any]:
        """
        Code Complexity Metrics for generated code.

        - Cyclomatic Complexity
        - Lines of Code (LOC)
        - Maintainability Index (MI)
        """
        metrics = {
            "loc": 0,
            "cyclomatic_complexity": 0,
            "maintainability_index": 0,
            "num_functions": 0,
            "num_classes": 0
        }

        for pf in self.result.get("parsed_files", []):
            content = pf.get("content", "")
            if not content:
                continue

            try:
                tree = ast.parse(content)
                metrics["num_functions"] += sum(1 for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
                metrics["num_classes"] += sum(1 for n in ast.walk(tree) if isinstance(n, ast.ClassDef))

                # Count lines
                non_empty_lines = [l for l in content.splitlines() if l.strip()]
                metrics["loc"] += len(non_empty_lines)

                # Cyclomatic complexity approximation
                metrics["cyclomatic_complexity"] += self._cyclomatic_complexity(tree)

            except SyntaxError:
                continue

        # Simplified Maintainability Index (0-100 scale)
        if metrics["loc"] > 0:
            # MI = 171 - 5.2 * ln(HV) - 0.23 * (Halstead Volume) - 16.2 * ln(LOC)
            # Simplified: MI ≈ 100 - (LOC/100) * 10 - complexity * 2
            mi = max(0, min(100, 100 - (metrics["loc"] / 100) * 10 - metrics["cyclomatic_complexity"] * 2))
            metrics["maintainability_index"] = round(mi, 2)

        return metrics

    def _cyclomatic_complexity(self, tree: ast.AST) -> int:
        """Calculate cyclomatic complexity of an AST."""
        complexity = 1  # Base complexity

        for node in ast.walk(tree):
            if isinstance(node, (ast.If, ast.While, ast.For, ast.ExceptHandler)):
                complexity += 1
            elif isinstance(node, ast.BoolOp):
                complexity += len(node.values) - 1  # AND/OR operators

        return complexity

    def compute_all_metrics(self) -> dict[str, Any]:
        """Compute all evaluation metrics."""
        metrics = {
            # Basic metrics
            "instance_id": self.instance_id,
            "repo": self.repo,
            "file_hit_rate": self.file_hit_rate(),
            "diff_generation_rate": self.diff_generation_rate(),
            "constraint_violation_rate": self.constraint_violation_rate(),
            "regression_rate": self.regression_rate(),  # -1 if not computed

            # Edit distance metrics
            "edit_distance": self.edit_distance(),

            # AST similarity
            "ast_similarity": self.ast_similarity(),

            # CodeBLEU approximation
            "codebleu_approx": self.codebleu_score(),

            # Complexity metrics
            "complexity_metrics": self.code_complexity_metrics(),

            # Runtime and cost
            "elapsed_s": self.result.get("elapsed_s", 0),
            "cost": self.result.get("cost", {}),

            # Gold info for reference
            "gold_files": self.gold_files,
            "predicted_files": self.predicted_files,
            "n_gold_files": len(self.gold_files),
            "n_predicted_files": len(self.predicted_files),
        }

        return metrics


def aggregate_metrics(metrics_list: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate per-instance metrics into summary statistics."""
    if not metrics_list:
        return {}

    n = len(metrics_list)

    # Basic metrics
    fhr_values = [m["file_hit_rate"] for m in metrics_list]
    dgr_values = [m["diff_generation_rate"] for m in metrics_list]
    cvr_values = [m["constraint_violation_rate"] for m in metrics_list if m["constraint_violation_rate"] >= 0]

    # Edit distance
    ed_values = [m["edit_distance"]["normalized"] for m in metrics_list]

    # AST similarity
    ast_values = [m["ast_similarity"]["mean_similarity"] for m in metrics_list]

    # CodeBLEU
    cb_values = [m["codebleu_approx"]["codebleu_approx"] for m in metrics_list]

    # Complexity
    loc_values = [m["complexity_metrics"]["loc"] for m in metrics_list]
    cc_values = [m["complexity_metrics"]["cyclomatic_complexity"] for m in metrics_list]
    mi_values = [m["complexity_metrics"]["maintainability_index"] for m in metrics_list]

    # Runtime
    runtime_values = [m["elapsed_s"] for m in metrics_list]

    return {
        "n_instances": n,
        "file_hit_rate": {
            "mean": round(sum(fhr_values) / n, 4),
            "std": round(_std(fhr_values), 4),
            "min": min(fhr_values),
            "max": max(fhr_values),
        },
        "diff_generation_rate": {
            "mean": round(sum(dgr_values) / n, 4),
        },
        "constraint_violation_rate": {
            "mean": round(sum(cvr_values) / len(cvr_values), 4) if cvr_values else -1,
        },
        "edit_distance_normalized": {
            "mean": round(sum(ed_values) / n, 4),
            "std": round(_std(ed_values), 4),
        },
        "ast_similarity": {
            "mean": round(sum(ast_values) / n, 4),
            "std": round(_std(ast_values), 4),
        },
        "codebleu_approx": {
            "mean": round(sum(cb_values) / n, 4),
            "std": round(_std(cb_values), 4),
        },
        "complexity_metrics": {
            "loc_mean": round(sum(loc_values) / n, 2),
            "cyclomatic_complexity_mean": round(sum(cc_values) / n, 2),
            "maintainability_index_mean": round(sum(mi_values) / n, 2),
        },
        "runtime_sec": {
            "mean": round(sum(runtime_values) / n, 2),
            "std": round(_std(runtime_values), 2),
            "total": round(sum(runtime_values), 2),
        },
    }


def _std(values: list[float]) -> float:
    """Calculate standard deviation."""
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    variance = sum((x - mean) ** 2 for x in values) / (len(values) - 1)
    return variance ** 0.5


# ── Patch Application Helpers ─────────────────────────────────────────────────

def apply_patch(repo_root: Path, patch_text: str) -> bool:
    """Apply a unified diff patch to a repository. Returns True on success."""
    if not patch_text.strip():
        return False

    try:
        result = subprocess.run(
            ["git", "apply", "--unsafe-paths"],
            input=patch_text,
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=60,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, Exception):
        return False


def revert_patch(repo_root: Path, patch_text: str) -> bool:
    """Revert a unified diff patch from a repository. Returns True on success."""
    if not patch_text.strip():
        return False

    try:
        result = subprocess.run(
            ["git", "apply", "--reverse", "--unsafe-paths"],
            input=patch_text,
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=60,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, Exception):
        return False
