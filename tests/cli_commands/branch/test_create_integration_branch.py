from unittest.mock import MagicMock

import pytest

from src.devrules.cli_commands.branch import (
    _get_available_branches_to_integrate_with,
    _get_integration_branch_name,
    _show_integration_options,
)


@pytest.mark.parametrize(
    "current_branch,branches_to_integrate,expected_messages",
    [
        (
            "feature/123",
            ["feature/456", "feature/789"],
            ["Base branch: feature/123", "1. feature/456", "2. feature/789"],
        ),
        (
            "feature/456",
            ["feature/123", "feature/789"],
            ["Base branch: feature/456", "1. feature/123", "2. feature/789"],
        ),
        (
            "feature/789",
            ["feature/123", "feature/456"],
            ["Base branch: feature/789", "1. feature/123", "2. feature/456"],
        ),
    ],
)
def test__show_integration_options(
    capsys, current_branch, branches_to_integrate, expected_messages
):
    _show_integration_options(current_branch, branches_to_integrate)
    captured = capsys.readouterr()
    for expected_message in expected_messages:
        assert expected_message in captured.out


@pytest.mark.parametrize(
    "current_branch,available_branches,selected_branches,expected_branches",
    [
        ("feature/789", ["feature/789"], None, None),  # only current branch available
        ("feature/456", ["feature/456", "feature/789"], [], None),  # no branches selected
        (
            "feature/456",
            ["feature/456", "feature/789", "bugfix/345"],
            ["bugfix/345"],
            ["bugfix/345"],
        ),  # only one branch selected
    ],
)
def test__get_available_branches_to_integrate_with(
    current_branch, available_branches, selected_branches, expected_branches, monkeypatch
):
    monkeypatch.setattr(
        "src.devrules.cli_commands.branch.get_existing_branches", lambda: available_branches
    )
    monkeypatch.setattr(
        "src.devrules.cli_commands.branch.prompter.choose_multiple",
        lambda *args, **kwargs: selected_branches,
    )
    if not expected_branches:
        with pytest.raises(SystemExit):
            _get_available_branches_to_integrate_with(current_branch)
    else:
        branches = _get_available_branches_to_integrate_with(current_branch)
        assert branches == expected_branches


@pytest.mark.parametrize(
    "prefix,branches_to_integrate,expected_branch_name",
    [
        ("custom", ["feature/123-new-stuff", "feature/456-another-feature"], "custom/123-456"),
        ("integration", ["feature/123-new-stuff", "bugfix/456-solve-issue"], "integration/123-456"),
    ],
)
def test__get_integration_branch_name(
    prefix, branches_to_integrate, expected_branch_name, monkeypatch
):
    config = MagicMock()
    config.branch = MagicMock()
    config.branch.pattern = r"^(custom|integration)[/-](\d+-)?[a-z0-9-]+$"
    config.branch.require_issue_number = True
    config.branch.prefixes = ["custom", "integration"]
    monkeypatch.setattr(
        "src.devrules.cli_commands.branch.prompter.write",
        lambda *args, **kwargs: kwargs.get("default"),
    )
    result = _get_integration_branch_name(config, prefix, branches_to_integrate)
    assert result == expected_branch_name
