import tempfile
from pathlib import Path
from typing import Generator

import pytest
from git import Repo

from devrules.config import Config


@pytest.fixture
def git_repo() -> Generator[Repo, None, None]:
    """Create a temporary git repository for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = Repo.init(tmpdir)

        # Configure git user for commits
        with repo.config_writer() as config:
            config.set_value("user", "name", "Test User")
            config.set_value("user", "email", "test@example.com")

        # Create initial commit
        readme = Path(tmpdir) / "README.md"
        readme.write_text("# Test Repository")
        repo.index.add([str(readme)])
        repo.index.commit("Initial commit")

        yield repo


@pytest.fixture
def config() -> Config:
    """Create test configuration."""
    from devrules.config import load_config

    config = load_config()
    config.deployment.migration_detection_enabled = True
    config.deployment.migration_paths = ["migrations/", "db/migrations/"]
    return config
