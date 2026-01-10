import subprocess
from unittest.mock import patch

import pytest

from devrules.config import PRConfig
from devrules.validators.pr_target import (
    check_pr_already_merged,
    suggest_pr_target,
    validate_pr_base_not_protected,
    validate_pr_target,
)


def pr_config_no_restrictions():
    """PR config with no target restrictions."""
    return PRConfig()


def pr_config_allowed_targets():
    """PR config with simple allowed targets."""
    return PRConfig(allowed_targets=["main", "develop", "staging"])


def pr_config_target_rules():
    """PR config with complex target rules."""
    return PRConfig(
        target_rules=[
            {
                "source_pattern": r"feature/.*",
                "allowed_targets": ["develop", "staging"],
                "disallowed_message": "Feature branches must target develop or staging",
            },
            {
                "source_pattern": r"hotfix/.*",
                "allowed_targets": ["main", "master"],
            },
        ]
    )


def pr_config_protected_prefixes():
    """PR config with protected branch prefixes."""
    return PRConfig(protected_branch_prefixes=["staging/", "qa/"])


@pytest.mark.parametrize(
    "source_branch,target_branch,config,expected_valid,expected_message",
    [
        # No restrictions configured
        (
            "feature/123-test",
            "main",
            pr_config_no_restrictions(),
            True,
            "No PR target restrictions configured",
        ),
        # Allowed targets - valid
        (
            "feature/123-test",
            "develop",
            pr_config_allowed_targets(),
            True,
            "Target branch 'develop' is valid",
        ),
        # Allowed targets - invalid
        (
            "feature/123-test",
            "invalid-target",
            pr_config_allowed_targets(),
            False,
            "Target branch 'invalid-target' is not in allowed list.\nAllowed targets: main, develop, staging",
        ),
        # Target rules - feature branch valid
        (
            "feature/123-test",
            "develop",
            pr_config_target_rules(),
            True,
            "Target branch 'develop' is valid",
        ),
        # Target rules - feature branch invalid with custom message
        (
            "feature/123-test",
            "main",
            pr_config_target_rules(),
            False,
            "Feature branches must target develop or staging",
        ),
        # Target rules - hotfix branch valid
        (
            "hotfix/urgent-fix",
            "main",
            pr_config_target_rules(),
            True,
            "Target branch 'main' is valid",
        ),
        # Target rules - hotfix branch invalid with default message
        (
            "hotfix/urgent-fix",
            "develop",
            pr_config_target_rules(),
            False,
            "Branch 'hotfix/urgent-fix' (matching pattern 'hotfix/.*') cannot target 'develop'.\nAllowed targets: main, master",
        ),
        # Branch not matching any rules - should pass since no restrictions apply
        (
            "random-branch",
            "main",
            pr_config_target_rules(),
            True,
            "Target branch 'main' is valid",
        ),
    ],
)
def test_validate_pr_target(source_branch, target_branch, config, expected_valid, expected_message):
    result, message = validate_pr_target(source_branch, target_branch, config)
    assert result == expected_valid
    assert message == expected_message


@pytest.mark.parametrize(
    "source_branch,config,expected_suggestion",
    [
        # Target rules - feature branch
        (
            "feature/123-test",
            pr_config_target_rules(),
            "develop",
        ),
        # Target rules - hotfix branch
        (
            "hotfix/urgent-fix",
            pr_config_target_rules(),
            "main",
        ),
        # Target rules - no match
        (
            "random-branch",
            pr_config_target_rules(),
            None,
        ),
        # Allowed targets with preferred branch
        (
            "feature/123-test",
            pr_config_allowed_targets(),
            "develop",
        ),
        # Allowed targets without preferred
        (
            "feature/123-test",
            PRConfig(allowed_targets=["main", "staging"]),
            "main",
        ),
        # No config - feature branch
        (
            "feature/123-test",
            pr_config_no_restrictions(),
            "develop",
        ),
        # No config - hotfix branch
        (
            "hotfix/urgent-fix",
            pr_config_no_restrictions(),
            "main",  # Would be get_default_branch(), but mocked to main
        ),
        # No config - release branch
        (
            "release/v1.0",
            pr_config_no_restrictions(),
            "main",
        ),
        # No config - other branch
        (
            "random-branch",
            pr_config_no_restrictions(),
            None,
        ),
    ],
)
def test_suggest_pr_target(source_branch, config, expected_suggestion):
    with patch("devrules.validators.pr_target.get_default_branch", return_value="main"):
        result = suggest_pr_target(source_branch, config)
        assert result == expected_suggestion


@pytest.mark.parametrize(
    "base_branch,protected_prefixes,expected_valid,expected_message",
    [
        # No protected prefixes configured
        (
            "feature/123-test",
            [],
            True,
            "No protected branch prefixes configured",
        ),
        # Valid branch - not protected
        (
            "feature/123-test",
            ["staging/", "qa/"],
            True,
            "Base branch 'feature/123-test' is not protected",
        ),
        # Protected branch - staging
        (
            "staging/feature-123",
            ["staging/", "qa/"],
            False,
            "Cannot create PR from protected branch 'staging/feature-123'. Protected branches (starting with 'staging/') should not be used as PR sources. They are meant for merging multiple features for testing.",
        ),
        # Protected branch - qa
        (
            "qa/hotfix-urgent",
            ["staging/", "qa/"],
            False,
            "Cannot create PR from protected branch 'qa/hotfix-urgent'. Protected branches (starting with 'qa/') should not be used as PR sources. They are meant for merging multiple features for testing.",
        ),
        # Branch starting with similar but not exact prefix
        (
            "mystaging/feature",
            ["staging/", "qa/"],
            True,
            "Base branch 'mystaging/feature' is not protected",
        ),
    ],
)
def test_validate_pr_base_not_protected(
    base_branch, protected_prefixes, expected_valid, expected_message
):
    result, message = validate_pr_base_not_protected(base_branch, protected_prefixes)
    assert result == expected_valid
    assert message == expected_message


@pytest.mark.parametrize(
    "source_branch,target_branch,mock_returncode,mock_stdout,mock_stderr,expected_merged,expected_message",
    [
        # Already merged - no unique commits
        (
            "feature/123-test",
            "main",
            0,
            "",
            "",
            True,
            "Branch 'feature/123-test' is already merged into 'main'",
        ),
        # Not merged - has unique commits
        (
            "feature/123-test",
            "main",
            0,
            "+ abc123\n+ def456",
            "",
            False,
            "Branch has unique commits",
        ),
        # Command fails
        (
            "feature/123-test",
            "main",
            1,
            "",
            "error",
            False,
            "Could not check merge status",
        ),
    ],
)
def test_check_pr_already_merged(
    source_branch,
    target_branch,
    mock_returncode,
    mock_stdout,
    mock_stderr,
    expected_merged,
    expected_message,
):
    mock_result = subprocess.CompletedProcess(
        args=["git", "cherry", target_branch, source_branch],
        returncode=mock_returncode,
        stdout=mock_stdout,
        stderr=mock_stderr,
    )

    with patch("subprocess.run", return_value=mock_result):
        result, message = check_pr_already_merged(source_branch, target_branch)
        assert result == expected_merged
        assert message == expected_message


def test_check_pr_already_merged_raises_exception():
    with patch("subprocess.run", side_effect=Exception):
        result, message = check_pr_already_merged("feature/test-source-branch", "develop")
        assert not result
        assert message == "Could not check merge status"
