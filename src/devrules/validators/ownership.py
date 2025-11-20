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
            "\"Your Name\"' or set the USER environment variable.",
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
