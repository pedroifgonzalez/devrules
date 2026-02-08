import pytest

from src.devrules.cli_commands.branch import _show_integration_options


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
