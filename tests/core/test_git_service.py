import subprocess
from unittest.mock import patch

import pytest

from devrules.core.git_service import (
    get_author,
    get_current_repo_name,
    remote_branch_exists,
    resolve_issue_branch,
)
from devrules.dtos.github import ProjectItem


@pytest.mark.parametrize(
    "title,branch_name",
    [
        ("This contains 'special' characters", "feature/12-this-contains-special-characters"),
        ("Add user authentication", "feature/12-add-user-authentication"),
        ("Fix bug #123", "feature/12-fix-bug-123"),
        ("Update README.md file", "feature/12-update-readmemd-file"),
        ("Handle (edge) cases [properly]", "feature/12-handle-edge-cases-properly"),
        ("Remove @deprecated methods", "feature/12-remove-deprecated-methods"),
        ("Support 100% coverage", "feature/12-support-100-coverage"),
        ("Add foo/bar endpoint", "feature/12-add-foobar-endpoint"),
        ("Multiple   spaces   here", "feature/12-multiple-spaces-here"),
        ("UPPERCASE TITLE", "feature/12-uppercase-title"),
        (" some spaces  ", "feature/12-some-spaces"),
    ],
)
def test_resolve_issue_branch(title, branch_name):
    output = resolve_issue_branch(scope="feature", project_item=ProjectItem(title=title), issue=12)
    assert output == branch_name


def test_get_author():
    # This test just checks that the function doesn't crash
    author = get_author()
    assert isinstance(author, str)
    assert len(author) > 0


def test_get_current_repo_name():
    current_repo = get_current_repo_name()
    assert isinstance(current_repo, str)
    assert current_repo == "devrules"


@pytest.mark.parametrize(
    "side_effect, expected",
    [
        (None, True),
        (subprocess.CalledProcessError(2, "git"), False),
    ],
)
def test_remote_branch_exists(side_effect, expected):
    with patch("subprocess.run") as mock_run:
        if side_effect:
            mock_run.side_effect = side_effect
        else:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout=b"",
                stderr=b"",
            )

        assert remote_branch_exists("main") is expected
