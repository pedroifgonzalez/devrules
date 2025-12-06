"""Tests for forbidden files validation."""

from unittest.mock import MagicMock, patch

from devrules.validators.forbidden_files import (
    check_forbidden_files,
    get_staged_files,
    matches_pattern,
    validate_no_forbidden_files,
)


def test_matches_pattern_simple():
    """Test simple glob pattern matching."""
    assert matches_pattern("file.log", "*.log") is True
    assert matches_pattern("file.txt", "*.log") is False
    assert matches_pattern("test.dump", "*.dump") is True


def test_matches_pattern_path():
    """Test path pattern matching."""
    assert matches_pattern("tmp/file.txt", "tmp/*") is True
    assert matches_pattern("cache/data.json", "cache/*") is True
    assert matches_pattern("src/file.py", "tmp/*") is False


def test_matches_pattern_nested():
    """Test nested path pattern matching."""
    assert matches_pattern("tmp/subdir/file.txt", "tmp/*") is True
    assert matches_pattern("src/tmp/file.txt", "tmp/*") is True
    assert matches_pattern("a/b/c/file.log", "*.log") is True


def test_matches_pattern_hidden_files():
    """Test matching hidden files and config files."""
    assert matches_pattern(".env.local", ".env*") is True
    assert matches_pattern(".env.production", ".env*") is True
    assert matches_pattern("config/.env.local", ".env*") is True


def test_check_forbidden_files_no_matches():
    """Test checking forbidden files with no matches."""
    files = ["src/main.py", "tests/test_main.py", "README.md"]
    forbidden_patterns = ["*.log", "*.dump"]
    forbidden_paths = ["tmp/", "cache/"]

    has_forbidden, forbidden_list = check_forbidden_files(
        files, forbidden_patterns, forbidden_paths
    )

    assert has_forbidden is False
    assert len(forbidden_list) == 0


def test_check_forbidden_files_pattern_match():
    """Test checking forbidden files with pattern matches."""
    files = ["src/main.py", "debug.log", "data.dump"]
    forbidden_patterns = ["*.log", "*.dump"]
    forbidden_paths = []

    has_forbidden, forbidden_list = check_forbidden_files(
        files, forbidden_patterns, forbidden_paths
    )

    assert has_forbidden is True
    assert len(forbidden_list) == 2
    assert any("debug.log" in item for item in forbidden_list)
    assert any("data.dump" in item for item in forbidden_list)


def test_check_forbidden_files_path_match():
    """Test checking forbidden files with path matches."""
    files = ["src/main.py", "tmp/cache.txt", "cache/data.json"]
    forbidden_patterns = []
    forbidden_paths = ["tmp/", "cache/"]

    has_forbidden, forbidden_list = check_forbidden_files(
        files, forbidden_patterns, forbidden_paths
    )

    assert has_forbidden is True
    assert len(forbidden_list) == 2
    assert any("tmp/cache.txt" in item for item in forbidden_list)
    assert any("cache/data.json" in item for item in forbidden_list)


def test_check_forbidden_files_multiple_matches():
    """Test checking forbidden files with multiple types of matches."""
    files = [
        "src/main.py",
        "debug.log",
        "tmp/data.txt",
        ".env.local",
        "cache/session.dat",
    ]
    forbidden_patterns = ["*.log", ".env*"]
    forbidden_paths = ["tmp/", "cache/"]

    has_forbidden, forbidden_list = check_forbidden_files(
        files, forbidden_patterns, forbidden_paths
    )

    assert has_forbidden is True
    assert len(forbidden_list) == 4  # log, env, tmp, cache


def test_check_forbidden_files_empty_rules():
    """Test checking forbidden files with no rules."""
    files = ["src/main.py", "debug.log", "tmp/data.txt"]
    forbidden_patterns = []
    forbidden_paths = []

    has_forbidden, forbidden_list = check_forbidden_files(
        files, forbidden_patterns, forbidden_paths
    )

    assert has_forbidden is False
    assert len(forbidden_list) == 0


@patch("devrules.validators.forbidden_files.subprocess.run")
def test_get_staged_files(mock_run):
    """Test getting staged files."""
    mock_run.return_value = MagicMock(
        stdout="file1.py\nfile2.py\nfile3.txt\n",
        returncode=0,
    )

    files = get_staged_files()

    assert len(files) == 3
    assert "file1.py" in files
    assert "file2.py" in files
    assert "file3.txt" in files


@patch("devrules.validators.forbidden_files.subprocess.run")
def test_get_staged_files_empty(mock_run):
    """Test getting staged files when none are staged."""
    mock_run.return_value = MagicMock(stdout="", returncode=0)

    files = get_staged_files()

    assert len(files) == 0


@patch("devrules.validators.forbidden_files.get_staged_files")
@patch("devrules.validators.forbidden_files.check_forbidden_files")
def test_validate_no_forbidden_files_valid(mock_check, mock_get_files):
    """Test validating when no forbidden files are found."""
    mock_get_files.return_value = ["src/main.py", "tests/test.py"]
    mock_check.return_value = (False, [])

    is_valid, message = validate_no_forbidden_files(
        forbidden_patterns=["*.log"],
        forbidden_paths=["tmp/"],
        check_staged=True,
    )

    assert is_valid is True
    assert "no forbidden files" in message.lower()


@patch("devrules.validators.forbidden_files.get_staged_files")
@patch("devrules.validators.forbidden_files.check_forbidden_files")
def test_validate_no_forbidden_files_invalid(mock_check, mock_get_files):
    """Test validating when forbidden files are found."""
    mock_get_files.return_value = ["src/main.py", "debug.log"]
    mock_check.return_value = (True, ["debug.log (matches pattern: *.log)"])

    is_valid, message = validate_no_forbidden_files(
        forbidden_patterns=["*.log"],
        forbidden_paths=[],
        check_staged=True,
    )

    assert is_valid is False
    assert "forbidden file" in message.lower()
    assert "debug.log" in message


@patch("devrules.validators.forbidden_files.get_staged_files")
def test_validate_no_forbidden_files_no_files(mock_get_files):
    """Test validating when no files are staged."""
    mock_get_files.return_value = []

    is_valid, message = validate_no_forbidden_files(
        forbidden_patterns=["*.log"],
        forbidden_paths=["tmp/"],
        check_staged=True,
    )

    assert is_valid is True
    assert "no files" in message.lower()


def test_validate_no_forbidden_files_no_rules():
    """Test validating when no rules are configured."""
    is_valid, message = validate_no_forbidden_files(
        forbidden_patterns=[],
        forbidden_paths=[],
        check_staged=True,
    )

    assert is_valid is True
    assert "no forbidden file rules" in message.lower()


def test_matches_pattern_editor_files():
    """Test matching common editor temporary files."""
    assert matches_pattern("file.swp", "*.swp") is True
    assert matches_pattern("file~", "*~") is True
    assert matches_pattern(".DS_Store", ".DS_Store") is True
    assert matches_pattern("Thumbs.db", "Thumbs.db") is True


def test_matches_pattern_case_sensitive():
    """Test that pattern matching is case-sensitive by default."""
    assert matches_pattern("File.LOG", "*.log") is False
    assert matches_pattern("file.log", "*.log") is True


def test_check_forbidden_files_complex_patterns():
    """Test checking with complex glob patterns."""
    files = [
        "src/app.py",
        "migrations/001_initial.sql",
        "backup/dump_20231201.sql",
        ".vscode/settings.json",
    ]
    forbidden_patterns = ["*.sql", ".vscode/*"]
    forbidden_paths = ["backup/"]

    has_forbidden, forbidden_list = check_forbidden_files(
        files, forbidden_patterns, forbidden_paths
    )

    assert has_forbidden is True
    # SQL files match pattern, backup matches path, vscode matches pattern
    assert len(forbidden_list) == 3
