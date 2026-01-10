"""Tests for branch validation."""

import pytest

from src.devrules.config import BranchConfig, GitHubConfig
from src.devrules.dtos.github import ProjectItem
from src.devrules.validators.branch import (
    _extract_issue_number,
    _get_environment,
    validate_branch,
    validate_cross_repo_card,
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


@pytest.mark.parametrize(
    "require_issue_number,branch,is_valid",
    [(True, "feature/123-login", True), (True, "feature/missing-issue-number", False)],
)
def test_validate_branch_issue_number(require_issue_number, branch, is_valid):
    config = BranchConfig(
        pattern=r"^(feature|bugfix)/(\d+-)?[a-z0-9-]+", prefixes=["feature", "bugfix"]
    )
    config.require_issue_number = require_issue_number
    result, _ = validate_branch(branch, config)
    assert result == is_valid


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


def test_single_branch_per_issue_same_branch_ignored():
    """Existing identical branch should be ignored when enforcing uniqueness."""

    existing = ["feature/123-same-branch"]

    is_valid, message = validate_single_branch_per_issue_env("feature/123-same-branch", existing)
    assert is_valid
    assert "one-branch" in message


def test_single_branch_per_issue_existing_without_issue():
    """Existing branches without issue numbers should not affect validation."""

    existing = ["feature/no-issue-branch"]

    is_valid, _ = validate_single_branch_per_issue_env("feature/123-valid-issue", existing)
    assert is_valid


def test_validate_cross_repo_card_skipped_when_unconfigured():
    """Cross-repo validation skips when GitHub repo is not configured."""

    github_config = GitHubConfig(owner=None, repo=None)
    project_item = ProjectItem(content={"repository": "owner/repo"})

    is_valid, message = validate_cross_repo_card(project_item, github_config)
    assert is_valid
    assert "not configured" in message


def test_validate_cross_repo_card_content_match():
    """Cross-repo validation passes when content repository matches."""

    github_config = GitHubConfig(owner="pedroifgonzalez", repo="devrules")
    project_item = ProjectItem(content={"repository": "pedroifgonzalez/devrules"})

    is_valid, message = validate_cross_repo_card(project_item, github_config)
    assert is_valid
    assert "configured repository" in message


def test_validate_cross_repo_card_repository_url_mismatch():
    """Cross-repo validation fails when repository URL belongs to another repo."""

    github_config = GitHubConfig(owner="pedroifgonzalez", repo="devrules")
    project_item = ProjectItem(repository="https://github.com/other/repo")

    is_valid, message = validate_cross_repo_card(project_item, github_config)
    assert not is_valid
    assert "does not match" in message


def test_validate_cross_repo_card_unknown_repository():
    """Cross-repo validation is skipped when repository cannot be determined."""

    github_config = GitHubConfig(owner="pedroifgonzalez", repo="devrules")
    project_item = ProjectItem()

    is_valid, message = validate_cross_repo_card(project_item, github_config)
    assert is_valid
    assert "could not be determined" in message
