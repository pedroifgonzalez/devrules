"""Pull request validation."""

import re
from devrules.config import PRConfig
from devrules.dtos.github import PRInfo


def validate_pr(pr_info: PRInfo, config: PRConfig) -> tuple:
    """Validate pull request against configuration rules."""
    messages = []
    is_valid = True

    total_loc = pr_info.additions + pr_info.deletions

    # Check title format
    if config.require_title_tag:
        pattern = re.compile(config.title_pattern)
        if pattern.match(pr_info.title):
            messages.append("✔ PR title valid")
        else:
            messages.append("✘ PR title does not follow required format")
            is_valid = False

    # Check LOC
    if total_loc > config.max_loc:
        messages.append(f"✘ PR too large: {total_loc} LOC (max: {config.max_loc})")
        is_valid = False
    else:
        messages.append(f"✔ PR size acceptable: {total_loc} LOC")

    # Check files
    if pr_info.changed_files > config.max_files:
        messages.append(f"✘ Too many files: {pr_info.changed_files} (max: {config.max_files})")
        is_valid = False
    else:
        messages.append(f"✔ File count acceptable: {pr_info.changed_files}")

    return is_valid, messages
