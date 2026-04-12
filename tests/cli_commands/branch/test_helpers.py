from unittest.mock import MagicMock

import pytest

from devrules.cli_commands.center import _get_issues_statuses_legend


@pytest.mark.parametrize(
    "status_emojis_mapping,status_issues,expected_legend",
    [
        (
            {"to_do": "🚀", "done": "✅"},
            {"To Do": ["Work on X", "Finish X"], "Done": ["Fix bug Y", "Implement feature Z"]},
            "🚀: To Do, ✅: Done",
        ),
        (
            {"to_do": "🚀"},
            {"To Do": ["Work on X", "Finish X"], "Done": ["Fix bug Y", "Implement feature Z"]},
            "🚀: To Do",
        ),
        (
            {"to_do": "🚀", "done": "✅"},
            {"To Do": ["Work on X", "Finish X"]},
            "🚀: To Do",
        ),
    ],
)
def test_get_issues_statuses_legend(status_emojis_mapping, status_issues, expected_legend):
    config = MagicMock()
    github_settings_mock = MagicMock()
    github_settings_mock.status_emojis = status_emojis_mapping
    config.github = github_settings_mock
    legend = _get_issues_statuses_legend(config=config, status_issues=status_issues)
    assert legend == expected_legend
