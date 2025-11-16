"""Branch name validation."""

import re
from devrules.config import BranchConfig


def validate_branch(branch_name: str, config: BranchConfig) -> tuple:
    """Validate branch name against configuration rules."""
    pattern = re.compile(config.pattern)

    if pattern.match(branch_name):
        return True, f"Branch name valid: {branch_name}"

    error_msg = f"Invalid branch name: {branch_name}\n"
    error_msg += f"Expected pattern: {config.pattern}\n"
    error_msg += f"Valid prefixes: {', '.join(config.prefixes)}"

    return False, error_msg
