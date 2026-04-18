"""Git history analyzer: extract design decisions from commit messages and file blame."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class CommitRecord:
    sha: str
    message: str
    author: str
    date: str
    files_changed: list[str] = field(default_factory=list)


@dataclass
class GitAnalysis:
    recent_commits: list[CommitRecord] = field(default_factory=list)
    design_decisions: list[str] = field(default_factory=list)
    hotspot_files: list[str] = field(default_factory=list)   # most frequently changed
    available: bool = True
    error: str = ""


# Keywords that hint at design decisions or constraints in commit messages
_DECISION_PATTERNS = [
    r"\bdo not\b", r"\bnever\b", r"\bmust\b", r"\balways\b",
    r"\brefactor\b", r"\bbreak.*change\b", r"\bdeprecate\b",
    r"\bfix.*race\b", r"\bthread.safe\b", r"\bcompat\b",
    r"\bapi.change\b", r"\brevert\b", r"\brollback\b",
    r"\bmigrat\b", r"\bschema\b", r"\bconstraint\b",
]
_COMPILED = [re.compile(p, re.IGNORECASE) for p in _DECISION_PATTERNS]


class GitHistorian:
    """Extract design decisions and hotspot info from git history.

    Falls back gracefully if git is not available or repo has no commits.
    """

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root

    def analyze(self, max_commits: int = 60, relevant_paths: list[str] | None = None) -> GitAnalysis:
        try:
            import git  # type: ignore[import]  # gitpython
        except ImportError:
            return GitAnalysis(
                available=False,
                error="gitpython not installed. Run: pip install gitpython",
            )

        try:
            repo = git.Repo(self.repo_root, search_parent_directories=True)
        except Exception as exc:
            return GitAnalysis(available=False, error=str(exc))

        try:
            commits = list(repo.iter_commits(max_count=max_commits))
        except Exception as exc:
            return GitAnalysis(available=False, error=str(exc))

        records: list[CommitRecord] = []
        file_change_count: dict[str, int] = {}
        decisions: list[str] = []

        for commit in commits:
            try:
                files_changed = list(commit.stats.files.keys())
            except Exception:
                files_changed = []

            for f in files_changed:
                file_change_count[f] = file_change_count.get(f, 0) + 1

            msg = commit.message.strip()
            records.append(
                CommitRecord(
                    sha=commit.hexsha[:8],
                    message=msg,
                    author=str(commit.author),
                    date=commit.authored_datetime.strftime("%Y-%m-%d"),
                    files_changed=files_changed,
                )
            )

            # Detect design-decision signals
            if any(p.search(msg) for p in _COMPILED):
                short = msg.splitlines()[0][:120]
                decisions.append(f"[{commit.hexsha[:7]}] {short}")

        hotspots = sorted(file_change_count, key=file_change_count.get, reverse=True)[:10]  # type: ignore[arg-type]

        return GitAnalysis(
            recent_commits=records,
            design_decisions=decisions[:20],
            hotspot_files=hotspots,
            available=True,
        )

    def commits_touching(self, rel_path: str, max_commits: int = 20) -> list[CommitRecord]:
        """Return commits that touched a specific file."""
        try:
            import git  # type: ignore[import]
            repo = git.Repo(self.repo_root, search_parent_directories=True)
            commits = list(repo.iter_commits(paths=rel_path, max_count=max_commits))
            return [
                CommitRecord(
                    sha=c.hexsha[:8],
                    message=c.message.strip(),
                    author=str(c.author),
                    date=c.authored_datetime.strftime("%Y-%m-%d"),
                )
                for c in commits
            ]
        except Exception:
            return []
