"""Pull request target branch validation."""

import re
import subprocess
from typing import List, Optional, Tuple

from devrules.config import PRConfig


def get_current_branch() -> Optional[str]:
    """Get the current git branch name.

    Returns:
        Branch name or None if error
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return None


def get_default_branch() -> str:
    """Get the default branch (main or master).

    Returns:
        Default branch name
    """
    try:
        # Try to get from remote
        result = subprocess.run(
            ["git", "symbolic-ref", "refs/remotes/origin/HEAD"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            # Output is like "refs/remotes/origin/main"
            return result.stdout.strip().split("/")[-1]
    except subprocess.CalledProcessError:
        pass

    # Fallback: check which exists
    for branch in ["main", "master"]:
        result = subprocess.run(
            ["git", "rev-parse", "--verify", f"refs/heads/{branch}"],
            capture_output=True,
        )  # type: ignore
        if result.returncode == 0:
            return branch

    return "main"  # Default fallback


def validate_pr_target(
    source_branch: str,
    target_branch: str,
    config: PRConfig,
) -> Tuple[bool, str]:
    """Validate that PR target branch is allowed.

    Args:
        source_branch: The branch creating the PR from
        target_branch: The branch targeting the PR to
        config: PR configuration

    Returns:
        Tuple of (is_valid, message)
    """
    # If no restrictions configured, allow any target
    if not config.allowed_targets and not config.target_rules:
        return True, "No PR target restrictions configured"

    # Check simple allowed targets list
    if config.allowed_targets:
        if target_branch not in config.allowed_targets:
            allowed = ", ".join(config.allowed_targets)
            return False, (
                f"Target branch '{target_branch}' is not in allowed list.\n"
                f"Allowed targets: {allowed}"
            )

    # Check complex target rules
    if config.target_rules:
        for rule in config.target_rules:
            if not isinstance(rule, dict):
                continue

            source_pattern = rule.get("source_pattern", "")
            allowed_targets = rule.get("allowed_targets", [])
            message = rule.get("disallowed_message", "")

            # Check if this rule applies to our source branch
            if source_pattern and re.match(source_pattern, source_branch):
                if target_branch not in allowed_targets:
                    if message:
                        return False, message
                    else:
                        targets_str = ", ".join(allowed_targets)
                        return False, (
                            f"Branch '{source_branch}' (matching pattern '{source_pattern}') "
                            f"cannot target '{target_branch}'.\n"
                            f"Allowed targets: {targets_str}"
                        )

    return True, f"Target branch '{target_branch}' is valid"


def suggest_pr_target(source_branch: str, config: PRConfig) -> Optional[str]:
    """Suggest appropriate PR target based on source branch.

    Args:
        source_branch: The source branch
        config: PR configuration

    Returns:
        Suggested target branch or None
    """
    # Check target rules for suggestions
    if config.target_rules:
        for rule in config.target_rules:
            if not isinstance(rule, dict):
                continue

            source_pattern = rule.get("source_pattern", "")
            allowed_targets = rule.get("allowed_targets", [])

            if source_pattern and re.match(source_pattern, source_branch):
                if allowed_targets:
                    # Return first allowed target as suggestion
                    return allowed_targets[0]

    # Check simple allowed targets
    if config.allowed_targets:
        # Prefer 'develop' or 'development' if in list
        for preferred in ["develop", "development", "dev"]:
            if preferred in config.allowed_targets:
                return preferred

        # Otherwise return first allowed
        if config.allowed_targets:
            return config.allowed_targets[0]

    # Default suggestions based on common patterns
    if source_branch.startswith("feature/") or source_branch.startswith("bugfix/"):
        return "develop"
    elif source_branch.startswith("hotfix/"):
        return get_default_branch()
    elif source_branch.startswith("release/"):
        return get_default_branch()

    return None


def validate_pr_base_not_protected(
    base_branch: str,
    protected_prefixes: List[str],
) -> Tuple[bool, str]:
    """Validate that base branch is not a protected staging branch.

    Args:
        base_branch: The base branch to check
        protected_prefixes: List of protected branch prefixes

    Returns:
        Tuple of (is_valid, message)
    """
    if not protected_prefixes:
        return True, "No protected branch prefixes configured"

    for prefix in protected_prefixes:
        if base_branch.startswith(prefix):
            return False, (
                f"Cannot create PR from protected branch '{base_branch}'. "
                f"Protected branches (starting with '{prefix}') should not be used as PR sources. "
                "They are meant for merging multiple features for testing."
            )

    return True, f"Base branch '{base_branch}' is not protected"


def get_merge_base(source_branch: str, target_branch: str) -> Optional[str]:
    """Get the common ancestor commit between two branches.

    Args:
        source_branch: Source branch
        target_branch: Target branch

    Returns:
        Commit SHA of merge base or None
    """
    try:
        result = subprocess.run(
            ["git", "merge-base", source_branch, target_branch],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return None


def check_pr_already_merged(source_branch: str, target_branch: str) -> Tuple[bool, str]:
    """Check if source branch is already merged into target.

    Args:
        source_branch: Source branch
        target_branch: Target branch

    Returns:
        Tuple of (is_merged, message)
    """
    try:
        # Check if all commits from source are in target
        result = subprocess.run(
            ["git", "cherry", target_branch, source_branch],
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            output = result.stdout.strip()
            if not output:
                # No unique commits, already merged
                return True, f"Branch '{source_branch}' is already merged into '{target_branch}'"

        return False, "Branch has unique commits"

    except subprocess.CalledProcessError:
        return False, "Could not check merge status"
