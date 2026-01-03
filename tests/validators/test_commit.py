"""Tests for commit message validation."""

from src.devrules.config import CommitConfig
from src.devrules.validators.commit import validate_commit


def test_valid_commit_messages():
    """Test that valid commit messages pass validation."""
    config = CommitConfig(
        tags=["FTR", "FIX", "DOCS"], pattern=r"^\[(FTR|FIX|DOCS)\].+", min_length=10, max_length=100
    )

    valid_messages = [
        "[FTR] Add new login feature",
        "[FIX] Resolve bug in payment",
        "[DOCS] Update README",
    ]

    for msg in valid_messages:
        is_valid, _ = validate_commit(msg, config)
        assert is_valid, f"{msg} should be valid"


def test_invalid_commit_messages():
    """Test that invalid commit messages fail validation."""
    config = CommitConfig(
        tags=["FTR", "FIX"], pattern=r"^\[(FTR|FIX)\].+", min_length=10, max_length=100
    )

    invalid_messages = [
        "No tag here",
        "[INVALID] Wrong tag",
        "[FTR] Short",
    ]

    for msg in invalid_messages:
        is_valid, _ = validate_commit(msg, config)
        assert not is_valid, f"{msg} should be invalid"
