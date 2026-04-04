"""Commit message validation."""

import re

from devrules.config import CommitConfig
from devrules.utils.commit_template import (
    DEFAULT_COMMIT_TEMPLATE,
    DEFAULT_CONTEXT_TEMPLATE,
    build_commit_example,
)


def validate_commit(message: str, config: CommitConfig) -> tuple:
    """Validate commit message against configuration rules."""
    pattern = re.compile(config.pattern)
    match = pattern.fullmatch(message)

    message_content = (
        match.groupdict().get("message", message).strip() if match else message.strip()
    )

    if len(message_content) < config.min_length:
        return False, f"Commit message too short (min: {config.min_length} chars)"

    if len(message_content) > config.max_length:
        return False, f"Commit message too long (max: {config.max_length} chars)"

    # Check pattern
    if match:
        return True, f"Commit message valid: {message}"

    template = config.template or DEFAULT_COMMIT_TEMPLATE
    context_template = config.context_template or DEFAULT_CONTEXT_TEMPLATE
    example = build_commit_example(config.tags, template, context_template)

    error_msg = f"Invalid commit message: {message}\n"
    error_msg += f"Expected format: {template}\n"
    error_msg += f"Example: {example}\n"
    error_msg += f"Valid tags: {', '.join(config.tags)}"

    return False, error_msg
