"""Core logic for Functional Groups management."""

import re
from typing import List, Optional

from devrules.config import Config, FunctionalGroupConfig


def resolve_group_for_branch(branch_name: str, config: Config) -> Optional[FunctionalGroupConfig]:
    """Resolve which functional group a branch belongs to based on patterns."""
    for _, group_config in config.functional_groups.items():
        if group_config.branch_pattern and re.match(group_config.branch_pattern, branch_name):
            return group_config
    return None


def get_valid_base_branches(group: FunctionalGroupConfig) -> List[str]:
    """Get list of valid base branches for a new feature in this group."""
    bases = [group.base_branch]
    if group.integration_cursor:
        bases.append(group.integration_cursor.branch)
    return list(set(bases))  # Deduplicate


def validate_branch_creation_base(base_branch: str, group: FunctionalGroupConfig) -> bool:
    """Check if the base branch is valid for creating a new feature in this group."""
    valid_bases = get_valid_base_branches(group)
    return base_branch in valid_bases


def calculate_merge_target(group: FunctionalGroupConfig) -> str:
    """Determine the correct merge target for a branch in this group."""
    if group.integration_cursor:
        return group.integration_cursor.branch
    return group.base_branch
