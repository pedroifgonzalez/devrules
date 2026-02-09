"""Branch ownership validation utilities."""

import os
import subprocess
from typing import Optional, Tuple

from loguru import logger

from devrules.core.git_service import get_author


def _git_config(key: str) -> Optional[str]:
    result = subprocess.run(
        ["git", "config", "--get", key],
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() or None


def validate_branch_ownership(current_branch: str) -> Tuple[bool, str]:
    """
    Validate that the current user is allowed to commit on the given branch.

    Rules:
    - Shared branches (main, master, develop, release/*) are always allowed.
    - If a branch owner was explicitly recorded (branch.<name>.owner),
      that owner is authoritative.
    - If the branch has no commits of its own (develop..HEAD is empty),
      the first commit is always allowed.
    - Otherwise, the first author in the branch history (after diverging
      from develop) is treated as the branch owner.
    """

    # Shared branches are always allowed
    if current_branch in ("main", "master", "develop") or current_branch.startswith("release/"):
        return True, "Shared branch — ownership check skipped"

    # Determine current user
    current_user = _git_config("user.name") or os.environ.get("USER", "")
    if not current_user:
        return (
            False,
            "Unable to determine current developer identity. "
            "Configure it with 'git config --global user.name \"Your Name\"'.",
        )

    # 🔐 1. Explicitly recorded branch owner (authoritative)
    recorded_owner = _git_config(f"branch.{current_branch}.owner")
    if recorded_owner:
        if recorded_owner != current_user:
            return (
                False,
                f"You are not allowed to commit on this branch. "
                f"Branch owner (recorded): {recorded_owner}, you: {current_user}",
            )
        return True, "Current user matches recorded branch owner"

    # 🔑 2. Check if the branch has any unique commits
    unique_commits = subprocess.run(
        ["git", "rev-list", "--count", "develop..HEAD"],
        capture_output=True,
        text=True,
    )

    if unique_commits.returncode == 0 and unique_commits.stdout.strip() == "0":
        return True, "New branch with no unique commits — first commit allowed"

    # 🧾 3. Fallback: infer owner from first unique commit author
    log_result = subprocess.run(
        ["git", "log", "develop..HEAD", "--format=%an", "--reverse"],
        capture_output=True,
        text=True,
    )

    authors = [line.strip() for line in log_result.stdout.splitlines() if line.strip()]
    if not authors:
        return True, "No author history detected — commit allowed"

    branch_owner = authors[0]
    if branch_owner != current_user:
        return (
            False,
            f"You are not allowed to commit on this branch. "
            f"Branch owner: {branch_owner}, your identity: {current_user}",
        )

    return True, "Current user matches branch owner"


def _get_current_user() -> str:
    """Return the current Git user.name or fall back to OS USER."""
    cmd = ["git", "config", "user.name"]
    logger.debug(f"Executing command: {' '.join(cmd)}")
    user_result = subprocess.run(cmd, capture_output=True, text=True)
    current_user = user_result.stdout.strip() or os.environ.get("USER", "")
    return current_user


def _get_merge_base(branch: str, base: str = "develop") -> str:
    """Return the merge-base commit hash between base and branch, or empty string."""

    try:
        result = subprocess.run(
            ["git", "merge-base", base, branch],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return ""


def _get_branch_owner(branch: str, current_user: str | None = None) -> str:
    """Determine the owner of a branch using the same logic as validate_branch_ownership.

    Returns:
        - "SHARED" for shared branches
        - Git username of the owner
    """

    if branch in ("main", "master", "develop") or branch.startswith("release/"):
        return "SHARED"

    merge_base = _get_merge_base(branch)
    log_range = f"{merge_base}..{branch}" if merge_base else branch

    log_result = subprocess.run(
        ["git", "log", log_range, "--format=%an", "--reverse"],
        capture_output=True,
        text=True,
    )

    current_user = current_user or get_author()
    authors = [line.strip() for line in log_result.stdout.splitlines() if line.strip()]

    if not authors:
        # If no unique commits (merged), check if branch tip is same as base tip
        # If same, assume new branch (owned by current user)
        # If different, assume old merged branch (check tip author)

        # Get base tip (develop)
        try:
            base_tip_result = subprocess.run(
                ["git", "rev-parse", "develop"],
                capture_output=True,
                text=True,
                check=True,
            )
            base_tip = base_tip_result.stdout.strip()

            branch_tip_result = subprocess.run(
                ["git", "rev-parse", branch],
                capture_output=True,
                text=True,
                check=True,
            )
            branch_tip = branch_tip_result.stdout.strip()

            if base_tip == branch_tip:
                return current_user

            # Different tips, check author of branch tip
            tip_log_result = subprocess.run(
                ["git", "log", "-1", "--format=%an", branch],
                capture_output=True,
                text=True,
                check=True,
            )
            tip_author = tip_log_result.stdout.strip()
            return tip_author

        except subprocess.CalledProcessError:
            return current_user

    return authors[0]


def list_user_owned_branches() -> list:
    """Return a list of local branches owned by the current user."""

    current_user = _get_current_user()
    if not current_user:
        raise RuntimeError(
            "Unable to determine current developer identity. "
            "Set it via 'git config --global user.name \"Your Name\"'."
        )

    branches_result = subprocess.run(
        ["git", "for-each-ref", "--format=%(refname:short)", "refs/heads/"],
        capture_output=True,
        text=True,
    )

    branches = branches_result.stdout.splitlines()
    owned_branches = []

    for branch in branches:
        owner = _get_branch_owner(branch, current_user)

        if owner == "SHARED":
            continue

        if owner == current_user:
            owned_branches.append(branch)

    return owned_branches
