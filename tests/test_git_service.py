import pytest

from devrules.dtos.github import ProjectItem
from src.devrules.core.git_service import resolve_issue_branch


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
