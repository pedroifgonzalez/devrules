"""Branch ownership validation utilities."""

import os
import subprocess
from typing import Tuple


def validate_branch_ownership(current_branch: str) -> Tuple[bool, str]:
    """Validate that the current user is allowed to commit on the given branch.

    Rules:
    - Shared branches (main, master, develop, release/*) are always allowed.
    - For other branches, the first author in the branch history (git log --reverse)
      is treated as the branch owner. Only that author may commit.
    - If there is no history yet, the first commit is allowed.
    """

    # Shared branches are always allowed
    if current_branch in ("main", "master", "develop") or current_branch.startswith("release/"):
        return True, "Shared branch — ownership check skipped"

    # Determine current user from git config, falling back to OS user
    user_result = subprocess.run(
        ["git", "config", "user.name"],
        capture_output=True,
        text=True,
    )
    current_user = user_result.stdout.strip() or os.environ.get("USER", "")

    if not current_user:
        return (
            False,
            "Unable to determine current developer identity. Configure it with 'git config --global user.name "
            '"Your Name"\' or set the USER environment variable.',
        )

    # Determine the base point with develop and only inspect commits after it
    try:
        merge_base_result = subprocess.run(
            ["git", "merge-base", "develop", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
        merge_base = merge_base_result.stdout.strip()
    except subprocess.CalledProcessError:
        # If we cannot find a merge-base (e.g., no common ancestor), fall back to full history
        merge_base = ""

    log_range = f"{merge_base}..HEAD" if merge_base else "HEAD"

    log_result = subprocess.run(
        ["git", "log", log_range, "--format=%an", "--reverse"],
        capture_output=True,
        text=True,
    )

    authors = [line.strip() for line in log_result.stdout.splitlines() if line.strip()]

    # If there is no history yet after the base (new branch), allow the first commit
    if not authors:
        return True, "New branch with no history after base — first commit allowed"

    branch_owner = authors[0]

    if branch_owner != current_user:
        return (
            False,
            f"You are not allowed to commit on this branch. Branch owner: {branch_owner}, your identity: {current_user}",
        )

    return True, "Current user matches branch owner"


def _get_current_user() -> str:
    """Return the current Git user.name or fall back to OS USER."""

    user_result = subprocess.run(["git", "config", "user.name"], capture_output=True, text=True)
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


def _get_branch_owner(branch: str, current_user: str) -> str:
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
