"""Tests for branch validation."""

from src.devrules.config import BranchConfig
from src.devrules.validators.branch import (
    _extract_issue_number,
    _get_environment,
    validate_branch,
    validate_single_branch_per_issue_env,
)


def test_valid_branch_names():
    """Test that valid branch names pass validation."""
    config = BranchConfig(
        pattern=r"^(feature|bugfix)/(\d+-)?[a-z0-9-]+", prefixes=["feature", "bugfix"]
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
        pattern=r"^(feature|bugfix)/(\d+-)?[a-z0-9-]+", prefixes=["feature", "bugfix"]
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


def test_get_environment_from_branch_name():
    """Environment should be staging when 'staging' is present, otherwise dev."""

    assert _get_environment("feature/123-login") == "dev"
    assert _get_environment("feature/123-login-staging") == "staging"
    assert _get_environment("bugfix/staging-456-fix") == "staging"


def test_extract_issue_number():
    """Issue number is extracted from conventional branch names, or None otherwise."""

    assert _extract_issue_number("feature/123-login") == "123"
    assert _extract_issue_number("bugfix/456-fix-bug") == "456"
    assert _extract_issue_number("feature/no-issue") is None


def test_single_branch_per_issue_per_environment():
    """Only one branch per issue per environment should be allowed."""

    existing = [
        "feature/123-add-login",  # dev env for issue 123
        "feature/123-add-login-staging",  # staging env for issue 123
        "feature/999-some-other",  # different issue
    ]

    # New dev branch for same issue should be rejected
    is_valid, _ = validate_single_branch_per_issue_env("feature/123-new-description", existing)
    assert not is_valid

    # New staging branch for same issue should be rejected
    is_valid, _ = validate_single_branch_per_issue_env(
        "feature/123-new-description-staging", existing
    )
    assert not is_valid

    # Different issue should be allowed
    is_valid, _ = validate_single_branch_per_issue_env("feature/456-another-thing", existing)
    assert is_valid

    # Branches without issue number should not trigger the rule
    is_valid, _ = validate_single_branch_per_issue_env("feature/no-issue", existing)
    assert is_valid
