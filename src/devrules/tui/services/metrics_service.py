"""Metrics service for analyzing git repository compliance."""

import subprocess
from dataclasses import dataclass
from typing import List

from devrules.config import load_config
from devrules.validators.branch import validate_branch
from devrules.validators.commit import validate_commit


@dataclass
class BranchMetrics:
    """Branch compliance metrics."""

    total_branches: int
    valid_branches: int
    invalid_branches: int
    compliance_percentage: float
    invalid_branch_names: List[str]


@dataclass
class CommitMetrics:
    """Commit message quality metrics."""

    total_commits: int
    valid_commits: int
    invalid_commits: int
    compliance_percentage: float


@dataclass
class RepositoryMetrics:
    """Overall repository metrics."""

    branch_metrics: BranchMetrics
    commit_metrics: CommitMetrics


class MetricsService:
    """Service for collecting and analyzing repository metrics."""

    def __init__(self, config_file: str | None = None):
        """Initialize metrics service.

        Args:
            config_file: Optional path to config file
        """
        self.config = load_config(config_file)

    def get_all_branches(self) -> List[str]:
        """Get all local branch names.

        Returns:
            List of branch names
        """
        try:
            result = subprocess.run(
                ["git", "branch", "--format=%(refname:short)"],
                capture_output=True,
                text=True,
                check=True,
            )
            branches = [b.strip() for b in result.stdout.strip().split("\n") if b.strip()]
            return branches
        except subprocess.CalledProcessError:
            return []

    def analyze_branches(self) -> BranchMetrics:
        """Analyze all branches for compliance.

        Returns:
            Branch metrics
        """
        branches = self.get_all_branches()
        total = len(branches)
        valid = 0
        invalid_names = []

        for branch in branches:
            is_valid, _ = validate_branch(branch, self.config.branch)
            if is_valid:
                valid += 1
            else:
                invalid_names.append(branch)

        invalid = total - valid
        compliance = (valid / total * 100) if total > 0 else 0.0

        return BranchMetrics(
            total_branches=total,
            valid_branches=valid,
            invalid_branches=invalid,
            compliance_percentage=compliance,
            invalid_branch_names=invalid_names,
        )

    def get_recent_commits(self, limit: int = 100) -> List[str]:
        """Get recent commit messages.

        Args:
            limit: Maximum number of commits to retrieve

        Returns:
            List of commit messages
        """
        try:
            result = subprocess.run(
                ["git", "log", f"-{limit}", "--pretty=format:%s"],
                capture_output=True,
                text=True,
                check=True,
            )
            messages = [m.strip() for m in result.stdout.strip().split("\n") if m.strip()]
            return messages
        except subprocess.CalledProcessError:
            return []

    def analyze_commits(self, limit: int = 100) -> CommitMetrics:
        """Analyze recent commits for compliance.

        Args:
            limit: Number of recent commits to analyze

        Returns:
            Commit metrics
        """
        messages = self.get_recent_commits(limit)
        total = len(messages)
        valid = 0

        for message in messages:
            is_valid, _ = validate_commit(message, self.config.commit)
            if is_valid:
                valid += 1

        invalid = total - valid
        compliance = (valid / total * 100) if total > 0 else 0.0

        return CommitMetrics(
            total_commits=total,
            valid_commits=valid,
            invalid_commits=invalid,
            compliance_percentage=compliance,
        )

    def get_repository_metrics(self) -> RepositoryMetrics:
        """Get comprehensive repository metrics.

        Returns:
            Repository metrics including branch and commit analysis
        """
        return RepositoryMetrics(
            branch_metrics=self.analyze_branches(),
            commit_metrics=self.analyze_commits(),
        )
