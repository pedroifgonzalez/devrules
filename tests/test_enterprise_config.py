"""Tests for enterprise configuration management."""

import os

import pytest
import toml

from devrules.enterprise.config import EnterpriseConfig
from devrules.enterprise.crypto import ConfigCrypto
from devrules.enterprise.integrity import IntegrityVerifier


class TestEnterpriseConfig:
    """Test enterprise configuration loading and management."""

    @pytest.fixture
    def temp_enterprise_dir(self, tmp_path):
        """Create temporary enterprise directory."""
        enterprise_dir = tmp_path / "enterprise"
        enterprise_dir.mkdir()
        return enterprise_dir

    @pytest.fixture
    def sample_config(self):
        """Sample enterprise configuration."""
        return {
            "enterprise": {
                "enabled": True,
                "locked": True,
                "integrity_check": True,
                "encryption": {
                    "sensitive_fields": ["github.api_url", "github.owner"],
                },
            },
            "branch": {
                "pattern": "^feature/.*",
                "prefixes": ["feature", "bugfix"],
            },
            "github": {
                "api_url": "https://github.company.com",
                "owner": "company-org",
            },
        }

    def test_is_enterprise_mode_false_when_no_config(self, temp_enterprise_dir):
        """Test enterprise mode detection when config doesn't exist."""
        config_mgr = EnterpriseConfig(temp_enterprise_dir)
        assert not config_mgr.is_enterprise_mode()

    def test_is_enterprise_mode_true_when_config_exists(self, temp_enterprise_dir, sample_config):
        """Test enterprise mode detection when config exists."""
        config_path = temp_enterprise_dir / ".devrules.enterprise.toml"
        with open(config_path, "w") as f:
            toml.dump(sample_config, f)

        config_mgr = EnterpriseConfig(temp_enterprise_dir)
        assert config_mgr.is_enterprise_mode()

    def test_load_enterprise_config(self, temp_enterprise_dir, sample_config):
        """Test loading enterprise configuration."""
        config_path = temp_enterprise_dir / ".devrules.enterprise.toml"
        with open(config_path, "w") as f:
            toml.dump(sample_config, f)

        config_mgr = EnterpriseConfig(temp_enterprise_dir)
        loaded_config = config_mgr.load_enterprise_config(decrypt=False)

        assert loaded_config is not None
        assert loaded_config["enterprise"]["enabled"] is True
        assert loaded_config["branch"]["pattern"] == "^feature/.*"

    def test_is_locked(self, temp_enterprise_dir, sample_config):
        """Test locked configuration detection."""
        config_path = temp_enterprise_dir / ".devrules.enterprise.toml"
        with open(config_path, "w") as f:
            toml.dump(sample_config, f)

        config_mgr = EnterpriseConfig(temp_enterprise_dir)
        assert config_mgr.is_locked()

    def test_is_not_locked(self, temp_enterprise_dir, sample_config):
        """Test unlocked configuration detection."""
        sample_config["enterprise"]["locked"] = False
        config_path = temp_enterprise_dir / ".devrules.enterprise.toml"
        with open(config_path, "w") as f:
            toml.dump(sample_config, f)

        config_mgr = EnterpriseConfig(temp_enterprise_dir)
        assert not config_mgr.is_locked()

    def test_get_sensitive_fields(self, temp_enterprise_dir, sample_config):
        """Test retrieving sensitive fields list."""
        config_path = temp_enterprise_dir / ".devrules.enterprise.toml"
        with open(config_path, "w") as f:
            toml.dump(sample_config, f)

        config_mgr = EnterpriseConfig(temp_enterprise_dir)
        fields = config_mgr.get_sensitive_fields()

        assert "github.api_url" in fields
        assert "github.owner" in fields

    def test_verify_integrity_success(self, temp_enterprise_dir, sample_config):
        """Test successful integrity verification."""
        config_path = temp_enterprise_dir / ".devrules.enterprise.toml"
        with open(config_path, "w") as f:
            toml.dump(sample_config, f)

        # Generate integrity hash
        integrity_hash = IntegrityVerifier.generate_hash(sample_config)
        integrity_path = temp_enterprise_dir / ".integrity.hash"
        with open(integrity_path, "w") as f:
            f.write(integrity_hash)

        config_mgr = EnterpriseConfig(temp_enterprise_dir)
        assert config_mgr.verify_integrity()

    def test_verify_integrity_failure(self, temp_enterprise_dir, sample_config):
        """Test integrity verification failure when config is modified."""
        config_path = temp_enterprise_dir / ".devrules.enterprise.toml"
        with open(config_path, "w") as f:
            toml.dump(sample_config, f)

        # Generate integrity hash
        integrity_hash = IntegrityVerifier.generate_hash(sample_config)
        integrity_path = temp_enterprise_dir / ".integrity.hash"
        with open(integrity_path, "w") as f:
            f.write(integrity_hash)

        # Modify config
        sample_config["branch"]["pattern"] = "^modified/.*"
        with open(config_path, "w") as f:
            toml.dump(sample_config, f)

        config_mgr = EnterpriseConfig(temp_enterprise_dir)
        assert not config_mgr.verify_integrity()

    def test_load_with_encryption(self, temp_enterprise_dir, sample_config):
        """Test loading config with encrypted fields."""
        # Encrypt sensitive fields
        key = ConfigCrypto.generate_key()
        crypto = ConfigCrypto(key)
        encrypted_config = crypto.encrypt_selective(
            sample_config, ["github.api_url", "github.owner"]
        )

        config_path = temp_enterprise_dir / ".devrules.enterprise.toml"
        with open(config_path, "w") as f:
            toml.dump(encrypted_config, f)

        # Set encryption key in environment
        os.environ["DEVRULES_ENTERPRISE_KEY"] = key.decode()

        try:
            config_mgr = EnterpriseConfig(temp_enterprise_dir)
            loaded_config = config_mgr.load_enterprise_config(decrypt=True)

            # Verify decryption
            assert loaded_config["github"]["api_url"] == "https://github.company.com"
            assert loaded_config["github"]["owner"] == "company-org"
        finally:
            del os.environ["DEVRULES_ENTERPRISE_KEY"]


class TestIntegrityVerifier:
    """Test integrity verification functionality."""

    def test_generate_hash(self):
        """Test hash generation."""
        config = {"test": "value", "nested": {"key": "data"}}
        hash1 = IntegrityVerifier.generate_hash(config)

        assert hash1 is not None
        assert len(hash1) == 64  # SHA-256 produces 64 hex characters

        # Same config should produce same hash
        hash2 = IntegrityVerifier.generate_hash(config)
        assert hash1 == hash2

    def test_verify_hash_success(self):
        """Test successful hash verification."""
        config = {"test": "value"}
        expected_hash = IntegrityVerifier.generate_hash(config)

        assert IntegrityVerifier.verify_hash(config, expected_hash)

    def test_verify_hash_failure(self):
        """Test hash verification failure."""
        config = {"test": "value"}
        wrong_hash = "0" * 64

        assert not IntegrityVerifier.verify_hash(config, wrong_hash)

    def test_hash_changes_with_config(self):
        """Test that hash changes when config changes."""
        config1 = {"test": "value1"}
        config2 = {"test": "value2"}

        hash1 = IntegrityVerifier.generate_hash(config1)
        hash2 = IntegrityVerifier.generate_hash(config2)

        assert hash1 != hash2

    def test_create_and_load_integrity_file(self, tmp_path):
        """Test creating and loading integrity file."""
        config = {"test": "value"}
        integrity_file = tmp_path / "integrity.hash"

        # Create integrity file
        IntegrityVerifier.create_integrity_file(config, str(integrity_file))
        assert integrity_file.exists()

        # Load and verify
        loaded_hash = IntegrityVerifier.load_integrity_file(str(integrity_file))
        assert IntegrityVerifier.verify_hash(config, loaded_hash)

    def test_verify_from_file_success(self, tmp_path):
        """Test verification from file."""
        config = {"test": "value"}
        integrity_file = tmp_path / "integrity.hash"

        IntegrityVerifier.create_integrity_file(config, str(integrity_file))
        assert IntegrityVerifier.verify_from_file(config, str(integrity_file))

    def test_verify_from_file_failure(self, tmp_path):
        """Test verification failure from file."""
        config1 = {"test": "value1"}
        config2 = {"test": "value2"}
        integrity_file = tmp_path / "integrity.hash"

        IntegrityVerifier.create_integrity_file(config1, str(integrity_file))
        assert not IntegrityVerifier.verify_from_file(config2, str(integrity_file))
