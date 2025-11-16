"""Tests for branch validation."""

from src.devrules.config import BranchConfig
from src.devrules.validators.branch import validate_branch


def test_valid_branch_names():
    """Test that valid branch names pass validation."""
    config = BranchConfig(
        pattern=r"^(feature|bugfix)/(\d+-)?[a-z0-9-]+",
        prefixes=["feature", "bugfix"]
    )

    valid_branches = [
        "feature/123-login",
        "bugfix/456-fix-bug",
        "feature/new-feature",
    ]

    for branch in valid_branches:
        is_valid, _ = validate_branch(branch, config)
        assert is_valid, f"{branch} should be valid"


def test_invalid_branch_names():
    """Test that invalid branch names fail validation."""
    config = BranchConfig(
        pattern=r"^(feature|bugfix)/(\d+-)?[a-z0-9-]+",
        prefixes=["feature", "bugfix"]
    )

    invalid_branches = [
        "main",
        "feature/UPPERCASE",
        "invalid/prefix",
        "feature-no-slash",
    ]

    for branch in invalid_branches:
        is_valid, _ = validate_branch(branch, config)
        assert not is_valid, f"{branch} should be invalid"
