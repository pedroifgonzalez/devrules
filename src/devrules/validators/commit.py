"""Commit message validation."""

import re

from devrules.config import CommitConfig


def validate_commit(message: str, config: CommitConfig) -> tuple:
    """Validate commit message against configuration rules."""
    pattern = re.compile(config.pattern)

    # Check length
    tag_found = re.search(r"\[(.*?)\]", message)
    message_content = message
    if tag_found:
        content = message.replace(tag_found.group(), "")
        message_content = content.strip()

    if len(message_content) < config.min_length:
        return False, f"Commit message too short (min: {config.min_length} chars)"

    if len(message_content) > config.max_length:
        return False, f"Commit message too long (max: {config.max_length} chars)"

    # Check pattern
    if pattern.match(message):
        return True, f"Commit message valid: {message}"

    error_msg = f"Invalid commit message: {message}\n"
    error_msg += "Expected format: [TAG] Message\n"
    error_msg += f"Valid tags: {', '.join(config.tags)}"

    return False, error_msg
