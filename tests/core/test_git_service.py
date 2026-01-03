import os
import subprocess
import tempfile
from unittest.mock import patch

import pytest
import typer
from git import Repo

from devrules.config import Config
from devrules.core.git_service import (
    detect_scope,
    ensure_git_repo,
    get_author,
    get_current_branch,
    get_current_repo_name,
    get_existing_branches,
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


def test_ensure_git_repo():
    ensure_git_repo()

    with pytest.raises(typer.Exit):
        with tempfile.TemporaryDirectory() as tmpdir:
            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                assert "tmp" in os.getcwd()
                ensure_git_repo()
            finally:
                os.chdir(original_cwd)


def test_current_branch(git_repo: Repo):
    test_branch = git_repo.create_head("test_branch")
    test_branch.checkout()
    original_cwd = os.getcwd()
    try:
        os.chdir(git_repo.working_dir)
        current_branch = get_current_branch()
    finally:
        os.chdir(original_cwd)
    assert current_branch == "test_branch"


def test_current_branch_no_repo_folder():
    original_cwd = os.getcwd()
    with pytest.raises(typer.Exit):
        with tempfile.TemporaryDirectory() as tmpdir:
            try:
                os.chdir(tmpdir)
                assert "tmp" in os.getcwd()
                _ = get_current_branch()
            finally:
                os.chdir(original_cwd)


def test_get_existing_branches(git_repo: Repo):
    original_cwd = os.getcwd()
    try:
        os.chdir(git_repo.working_dir)

        # arrange
        main = git_repo.create_head("main")
        main.checkout()

        develop = git_repo.create_head("develop")
        develop.checkout()

        # act
        branches = get_existing_branches()

        # assert
        assert set(branches) == {"main", "develop", "master"}
    finally:
        os.chdir(original_cwd)


def test_get_existing_branches_no_repo_folder():
    with tempfile.TemporaryDirectory() as tmpdir:
        original_cwd = os.getcwd()
        try:
            os.chdir(tmpdir)
            assert "tmp" in os.getcwd()
            branches = get_existing_branches()
            assert branches == []
        finally:
            os.chdir(original_cwd)


@pytest.mark.parametrize(
    "labels_hierarchy,project_item_labels,expected_scope",
    [
        (["bug", "enhancement", "documentation"], ["enhancement", "documentation"], "feature"),
        (["bug", "documentation", "enhancement"], ["documentation", "enhancement"], "docs"),
        (
            ["bug", "documentation", "enhancement"],
            ["documentation", "enhancement", "bug"],
            "bugfix",
        ),
    ],
)
def test_detect_scope(config: Config, labels_hierarchy, project_item_labels, expected_scope):
    config.branch.labels_hierarchy = labels_hierarchy
    config.branch.labels_mapping = {
        "bug": "bugfix",
        "enhancement": "feature",
        "documentation": "docs",
    }
    pi = ProjectItem(labels=project_item_labels)
    scope = detect_scope(config=config, project_item=pi)
    assert scope == expected_scope
