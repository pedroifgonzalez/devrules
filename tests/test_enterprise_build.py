"""Integration tests for enterprise build workflow."""

import os
import shutil

import pytest
import toml

from devrules.enterprise.builder import EnterpriseBuilder
from devrules.enterprise.crypto import ConfigCrypto


class TestEnterpriseBuild:
    """Integration tests for enterprise build process."""

    @pytest.fixture
    def project_root(self, tmp_path):
        """Create a minimal project structure for testing."""
        project = tmp_path / "test_project"
        project.mkdir()

        # Create pyproject.toml
        pyproject = {
            "project": {
                "name": "test-devrules",
                "version": "0.1.0",
                "dependencies": [],
            }
        }
        with open(project / "pyproject.toml", "w") as f:
            toml.dump(pyproject, f)

        # Create src structure
        src_dir = project / "src" / "devrules"
        src_dir.mkdir(parents=True)
        (src_dir / "__init__.py").write_text("")

        return project

    @pytest.fixture
    def enterprise_config(self):
        """Sample enterprise configuration."""
        return {
            "enterprise": {
                "enabled": True,
                "locked": True,
                "integrity_check": True,
                "encryption": {
                    "sensitive_fields": ["github.api_url"],
                },
            },
            "branch": {
                "pattern": "^feature/.*",
                "prefixes": ["feature"],
            },
            "github": {
                "api_url": "https://github.company.com",
                "owner": "test-org",
            },
        }

    def test_embed_config(self, project_root, enterprise_config, tmp_path):
        """Test embedding configuration into package."""
        # Create config file
        config_file = tmp_path / "enterprise.toml"
        with open(config_file, "w") as f:
            toml.dump(enterprise_config, f)

        builder = EnterpriseBuilder(project_root)
        config_path, key = builder.embed_config(str(config_file), encrypt=False)

        # Verify config was embedded
        assert config_path.exists()
        assert config_path.name == ".devrules.enterprise.toml"

        # Verify integrity file was created
        integrity_path = project_root / "src" / "devrules" / "enterprise" / ".integrity.hash"
        assert integrity_path.exists()

    def test_embed_config_with_encryption(self, project_root, enterprise_config, tmp_path):
        """Test embedding configuration with encryption."""
        config_file = tmp_path / "enterprise.toml"
        with open(config_file, "w") as f:
            toml.dump(enterprise_config, f)

        builder = EnterpriseBuilder(project_root)
        config_path, key = builder.embed_config(
            str(config_file),
            encrypt=True,
            sensitive_fields=["github.api_url"],
        )

        # Verify encryption key was generated
        assert key is not None

        # Load embedded config and verify encryption
        embedded_config = toml.load(config_path)
        crypto = ConfigCrypto(key)
        assert crypto.is_encrypted(embedded_config["github"]["api_url"])

    def test_modify_package_metadata(self, project_root):
        """Test modifying package metadata."""
        builder = EnterpriseBuilder(project_root)
        builder.modify_package_metadata(
            package_name="test-devrules-company",
            version_suffix="enterprise",
        )

        # Verify modifications
        pyproject = toml.load(project_root / "pyproject.toml")
        assert pyproject["project"]["name"] == "test-devrules-company"
        assert pyproject["project"]["version"] == "0.1.0+enterprise"

    def test_restore_package_metadata(self, project_root):
        """Test restoring original package metadata."""
        # Backup original
        backup_path = project_root / "pyproject.toml.backup"
        shutil.copy(project_root / "pyproject.toml", backup_path)

        # Modify
        builder = EnterpriseBuilder(project_root)
        builder.modify_package_metadata(package_name="modified")

        # Restore
        builder.restore_package_metadata(backup_path)

        # Verify restoration
        pyproject = toml.load(project_root / "pyproject.toml")
        assert pyproject["project"]["name"] == "test-devrules"

    def test_cleanup_embedded_config(self, project_root, enterprise_config, tmp_path):
        """Test cleaning up embedded configuration."""
        config_file = tmp_path / "enterprise.toml"
        with open(config_file, "w") as f:
            toml.dump(enterprise_config, f)

        builder = EnterpriseBuilder(project_root)
        config_path, _ = builder.embed_config(str(config_file), encrypt=False)

        # Verify config exists
        assert config_path.exists()

        # Cleanup
        builder.cleanup_embedded_config()

        # Verify cleanup
        assert not config_path.exists()

    def test_create_distribution_readme(self, project_root):
        """Test creating distribution README."""
        builder = EnterpriseBuilder(project_root)
        readme = builder.create_distribution_readme(
            package_name="test-devrules-company",
            has_encryption=True,
        )

        # Verify README content
        assert "test-devrules-company" in readme
        assert "Encryption Key" in readme
        assert "DEVRULES_ENTERPRISE_KEY" in readme

    def test_create_distribution_readme_no_encryption(self, project_root):
        """Test creating distribution README without encryption."""
        builder = EnterpriseBuilder(project_root)
        readme = builder.create_distribution_readme(
            package_name="test-devrules-company",
            has_encryption=False,
        )

        # Verify README content
        assert "test-devrules-company" in readme
        assert "Encryption Key" not in readme


class TestConfigurationPriority:
    """Test configuration priority system."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create temporary project with configs."""
        project = tmp_path / "project"
        project.mkdir()

        # Create user config
        user_config = {
            "branch": {"pattern": "^user/.*", "prefixes": ["user"]},
            "commit": {"tags": ["USER"]},
        }
        with open(project / ".devrules.toml", "w") as f:
            toml.dump(user_config, f)

        return project

    def test_user_config_loads_without_enterprise(self, temp_project):
        """Test that user config loads when no enterprise config exists."""
        from devrules.config import load_config

        os.chdir(temp_project)
        config = load_config()

        # User config should be loaded
        assert config.branch.pattern == "^user/.*"

    def test_enterprise_config_overrides_user_when_locked(self, temp_project, tmp_path):
        """Test that locked enterprise config overrides user config."""
        # This test would require actually installing the package with enterprise config
        # For now, we'll skip it as it requires a full build/install cycle
        pytest.skip("Requires full package installation")


class TestTamperingDetection:
    """Test tampering detection functionality."""

    def test_integrity_check_detects_modification(self, tmp_path):
        """Test that integrity check detects config modification."""
        from devrules.enterprise.config import EnterpriseConfig
        from devrules.enterprise.integrity import IntegrityVerifier

        # Create enterprise config with integrity_check enabled
        config = {
            "enterprise": {"integrity_check": True},
            "test": "value",
        }
        config_path = tmp_path / ".devrules.enterprise.toml"
        with open(config_path, "w") as f:
            toml.dump(config, f)

        # Create integrity file
        integrity_path = tmp_path / ".integrity.hash"
        IntegrityVerifier.create_integrity_file(config, str(integrity_path))

        # Verify integrity passes
        config_mgr = EnterpriseConfig(tmp_path)
        assert config_mgr.verify_integrity()

        # Modify config
        config["test"] = "modified"
        with open(config_path, "w") as f:
            toml.dump(config, f)

        # Verify integrity fails (need new instance to reload config)
        config_mgr = EnterpriseConfig(tmp_path)
        assert not config_mgr.verify_integrity()
