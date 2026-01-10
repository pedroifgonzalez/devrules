import subprocess
from unittest.mock import patch

import pytest

from devrules.config import DocumentationRule
from devrules.validators.documentation import (
    _format_docs_list,
    display_documentation_guidance,
    find_matching_rules,
    format_documentation_message,
    get_changed_files,
    get_relevant_documentation,
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
    "files,rules,expected_matches",
    [
        # No matches
        (
            ["readme.txt"],
            [doc_rule_simple()],
            [],
        ),
        # Single match
        (
            ["script.py"],
            [doc_rule_simple()],
            [("script.py", doc_rule_simple())],
        ),
        # Multiple files, one rule
        (
            ["script.py", "main.py", "readme.txt"],
            [doc_rule_simple()],
            [("script.py", doc_rule_simple())],
        ),
        # Multiple rules, multiple matches
        (
            ["script.py", "migrations/001.sql", "api/users.py"],
            [doc_rule_simple(), doc_rule_with_message(), doc_rule_with_checklist()],
            [
                ("script.py", doc_rule_simple()),
                ("migrations/001.sql", doc_rule_with_message()),
                ("api/users.py", doc_rule_with_checklist()),
            ],
        ),
        # Duplicate rules avoided (same pattern and docs_url)
        (
            ["script.py", "main.py"],
            [doc_rule_simple(), doc_rule_simple()],  # Same rule twice
            [("script.py", doc_rule_simple())],  # Only one match
        ),
        # Empty files list
        (
            [],
            [doc_rule_simple()],
            [],
        ),
        # Empty rules list
        (
            ["script.py"],
            [],
            [],
        ),
    ],
)
def test_find_matching_rules(files, rules, expected_matches):
    result = find_matching_rules(files, rules)

    # Convert to comparable format (rule objects to their key properties)
    result_formatted = [(file, f"{rule.file_pattern}:{rule.docs_url}") for file, rule in result]
    expected_formatted = [
        (file, f"{rule.file_pattern}:{rule.docs_url}") for file, rule in expected_matches
    ]

    assert result_formatted == expected_formatted


def test_format_documentation_message_no_matches():
    """Test format_documentation_message with no matches."""
    result = format_documentation_message([])
    assert result == ""


def test_format_documentation_message_with_matches():
    """Test format_documentation_message with matches."""
    matches = [
        ("script.py", doc_rule_simple()),
        ("migrations/001.sql", doc_rule_with_message()),
        ("api/users.py", doc_rule_with_checklist()),
    ]

    result = format_documentation_message(matches, show_files=True)

    # Should contain expected content
    assert "📚 Context-Aware Documentation" in result
    assert "Pattern: *.py" in result
    assert "Pattern: migrations/**" in result
    assert "Pattern: api/*.py" in result
    assert "https://example.com/python" in result
    assert "Remember to run migrations after deployment" in result
    assert "Update API version" in result
    assert "Test backwards compatibility" in result
    assert "Update client libraries" in result


def test_format_documentation_message_hide_files():
    """Test format_documentation_message with show_files=False."""
    matches = [("script.py", doc_rule_simple())]
    result = format_documentation_message(matches, show_files=False)

    # Should not show file names
    assert "script.py" not in result
    assert "Pattern: *.py" in result


@pytest.mark.parametrize(
    "rule_groups,show_files,expected_contains,invert_expectation",
    [
        # Simple rule group
        (
            {
                "*.py:": {
                    "rule": doc_rule_simple(),
                    "files": ["script.py", "main.py"],
                }
            },
            True,
            ["Pattern: *.py", "Files: script.py, main.py", "🔗 Docs: https://example.com/python"],
            False,
        ),
        # Rule with message
        (
            {
                "migrations/**:": {
                    "rule": doc_rule_with_message(),
                    "files": ["migrations/001.sql"],
                }
            },
            True,
            [
                "Pattern: migrations/**",
                "Files: migrations/001.sql",
                "ℹ️  Remember to run migrations after deployment",
            ],
            False,
        ),
        # Rule with checklist
        (
            {
                "api/*.py:": {
                    "rule": doc_rule_with_checklist(),
                    "files": ["api/users.py"],
                }
            },
            True,
            ["Pattern: api/*.py", "Files: api/users.py", "✅ Checklist:", "• Update API version"],
            False,
        ),
        # Hide files
        (
            {
                "*.py:": {
                    "rule": doc_rule_simple(),
                    "files": ["script.py"],
                }
            },
            False,
            ["Pattern: *.py"],
            False,
        ),
        # Many files
        (
            {
                "*.py:": {
                    "rule": doc_rule_simple(),
                    "files": ["f1.py", "f2.py", "f3.py", "f4.py", "f5.py", "f6.py"],
                }
            },
            True,
            ["Pattern: *.py", "Files: 6 file(s) matched"],
            False,
        ),
    ],
)
def test_format_docs_list(rule_groups, show_files, expected_contains, invert_expectation):
    result = _format_docs_list(rule_groups, show_files)

    assert "📚 Context-Aware Documentation" in result
    assert "=" * 50 in result

    for item in expected_contains:
        if invert_expectation:
            assert item not in result
        else:
            assert item in result


@pytest.mark.parametrize(
    "rules,base_branch,mock_changed_files,expected_has_docs,expected_contains",
    [
        # No rules
        (
            [],
            "HEAD",
            ["script.py"],
            False,
            "",
        ),
        # No changed files
        (
            [doc_rule_simple()],
            "HEAD",
            [],
            False,
            "",
        ),
        # No matches
        (
            [doc_rule_simple()],
            "HEAD",
            ["readme.txt"],
            False,
            "",
        ),
        # Has matches
        (
            [doc_rule_simple()],
            "HEAD",
            ["script.py"],
            True,
            ["Pattern: *.py", "https://example.com/python"],
        ),
        # Multiple matches
        (
            [doc_rule_simple(), doc_rule_with_message()],
            "develop",
            ["script.py", "migrations/001.sql"],
            True,
            ["Pattern: *.py", "Pattern: migrations/**"],
        ),
    ],
)
def test_get_relevant_documentation(
    rules, base_branch, mock_changed_files, expected_has_docs, expected_contains
):
    with patch(
        "devrules.validators.documentation.get_changed_files", return_value=mock_changed_files
    ):
        has_docs, message = get_relevant_documentation(rules, base_branch)

        assert has_docs == expected_has_docs

        if expected_has_docs:
            assert message != ""
            for item in expected_contains:
                assert item in message
        else:
            assert message == expected_contains  # Should be empty string


@pytest.mark.parametrize(
    "rules,base_branch,mock_has_docs,mock_message,expected_return,expected_output",
    [
        # No documentation
        (
            [doc_rule_simple()],
            "HEAD",
            False,
            "",
            False,
            "",
        ),
        # Has documentation
        (
            [doc_rule_simple()],
            "HEAD",
            True,
            "📚 Context-Aware Documentation\nPattern: *.py",
            True,
            "📚 Context-Aware Documentation\nPattern: *.py\n",
        ),
    ],
)
def test_display_documentation_guidance(
    rules, base_branch, mock_has_docs, mock_message, expected_return, expected_output, capsys
):
    with patch(
        "devrules.validators.documentation.get_relevant_documentation",
        return_value=(mock_has_docs, mock_message),
    ):
        result = display_documentation_guidance(rules, base_branch)

        assert result == expected_return

        captured = capsys.readouterr()
        assert captured.out == expected_output


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
