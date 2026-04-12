import subprocess
from unittest.mock import patch

import pytest

from devrules.config import DocumentationRule
from devrules.validators.documentation import (
    get_changed_files,
    matches_file_pattern,
    validate_documentation_patterns,
)


def doc_rule_simple():
    """Simple documentation rule."""
    return DocumentationRule(
        file_pattern="*.py",
        docs_url="https://example.com/python",
    )


def doc_rule_with_message():
    """Documentation rule with message."""
    return DocumentationRule(
        file_pattern="migrations/**",
        message="Remember to run migrations after deployment",
    )


def doc_rule_with_checklist():
    """Documentation rule with checklist."""
    return DocumentationRule(
        file_pattern="api/*.py",
        docs_url="https://api-docs.example.com",
        checklist=[
            "Update API version",
            "Test backwards compatibility",
            "Update client libraries",
        ],
    )


def doc_rule_invalid():
    """Invalid documentation rule."""
    return DocumentationRule(
        file_pattern="",
        docs_url="",
        message="",
        checklist=[],
    )


@pytest.mark.parametrize(
    "base_branch,mock_stdout,mock_stderr,mock_returncode,expected_files,mock_exception",
    [
        # HEAD branch - staged files
        (
            "HEAD",
            "file1.py\nfile2.py\n\n",
            "",
            0,
            ["file1.py", "file2.py"],
            None,
        ),
        # HEAD branch - no files
        (
            "HEAD",
            "",
            "",
            0,
            [],
            None,
        ),
        # Specific branch
        (
            "develop",
            "api/v1.py\nmigrations/001.sql\n",
            "",
            0,
            ["api/v1.py", "migrations/001.sql"],
            None,
        ),
        # Command fails
        (
            "HEAD",
            "",
            "error",
            1,
            [],
            None,
        ),
        # Command raises exception
        (
            "HEAD",
            None,
            None,
            None,
            [],
            subprocess.CalledProcessError(1, "git"),
        ),
    ],
)
def test_get_changed_files(
    base_branch, mock_stdout, mock_stderr, mock_returncode, expected_files, mock_exception
):
    if mock_exception:
        mock_side_effect = mock_exception
        mock_return = None
    else:
        mock_result = subprocess.CompletedProcess(
            args=(
                ["git", "diff", "--cached", "--name-only"]
                if base_branch == "HEAD"
                else ["git", "diff", "--name-only", base_branch]
            ),
            returncode=mock_returncode,
            stdout=mock_stdout,
            stderr=mock_stderr,
        )
        mock_side_effect = None
        mock_return = mock_result

    with patch(
        "subprocess.run", return_value=mock_return, side_effect=mock_side_effect
    ) as mock_run:
        result = get_changed_files(base_branch)
        assert result == expected_files

        # Verify correct command was called
        if not mock_exception:
            if base_branch == "HEAD":
                mock_run.assert_called_once_with(
                    ["git", "diff", "--cached", "--name-only"],
                    capture_output=True,
                    text=True,
                    check=True,
                )
            else:
                mock_run.assert_called_once_with(
                    ["git", "diff", "--name-only", base_branch],
                    capture_output=True,
                    text=True,
                    check=True,
                )


@pytest.mark.parametrize(
    "file_path,pattern,expected",
    [
        # Direct matches
        ("file.py", "file.py", True),
        ("file.py", "*.py", True),
        ("file.py", "*.txt", False),
        ("dir/file.py", "dir/*.py", True),
        ("dir/file.py", "dir/file.py", True),
        ("dir/file.py", "other/*.py", False),
        # Recursive patterns with **
        ("migrations/001.sql", "migrations/**", True),
        ("migrations/versions/001.sql", "migrations/**", True),
        ("api/v1/users.py", "api/**", True),
        ("src/api/v1/users.py", "api/**", True),
        ("some/migrations/001.sql", "migrations/**", True),
        # Edge cases
        ("file", "*", True),
        ("file.py", "", False),
        ("", "*.py", False),
    ],
)
def test_matches_file_pattern(file_path, pattern, expected):
    result = matches_file_pattern(file_path, pattern)
    assert result == expected


@pytest.mark.parametrize(
    "rules,expected_errors",
    [
        # Valid rules
        (
            [doc_rule_simple(), doc_rule_with_message(), doc_rule_with_checklist()],
            [],
        ),
        # Missing file_pattern
        (
            [doc_rule_invalid()],
            [
                "Rule #1: file_pattern is required",
                "Rule #1 (): Must provide at least one of: docs_url, message, or checklist",
            ],
        ),
        # Missing all required fields
        (
            [
                DocumentationRule(
                    file_pattern="",
                    docs_url="",
                    message="",
                    checklist=[],
                )
            ],
            [
                "Rule #1: file_pattern is required",
                "Rule #1 (): Must provide at least one of: docs_url, message, or checklist",
            ],
        ),
        # Has docs_url but no file_pattern
        (
            [
                DocumentationRule(
                    file_pattern="",
                    docs_url="https://example.com",
                    message="",
                    checklist=[],
                )
            ],
            ["Rule #1: file_pattern is required"],
        ),
        # Multiple rules with different errors
        (
            [
                doc_rule_simple(),  # Valid
                DocumentationRule(
                    file_pattern="",
                    docs_url="",
                    message="",
                    checklist=[],
                ),  # Invalid
                DocumentationRule(
                    file_pattern="api/**",
                    docs_url="",
                    message="",
                    checklist=[],
                ),  # Missing info
            ],
            [
                "Rule #2: file_pattern is required",
                "Rule #2 (): Must provide at least one of: docs_url, message, or checklist",
                "Rule #3 (api/**): Must provide at least one of: docs_url, message, or checklist",
            ],
        ),
    ],
)
def test_validate_documentation_patterns(rules, expected_errors):
    result = validate_documentation_patterns(rules)
    assert result == expected_errors
