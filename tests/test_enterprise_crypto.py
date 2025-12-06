"""Tests for enterprise encryption functionality."""

import pytest

from devrules.enterprise.crypto import ConfigCrypto


class TestConfigCrypto:
    """Test encryption and decryption functionality."""

    def test_generate_key(self):
        """Test key generation."""
        key = ConfigCrypto.generate_key()
        assert key is not None
        assert len(key) == 44  # Fernet keys are 44 bytes when base64 encoded

    def test_derive_key_from_password(self):
        """Test key derivation from password."""
        password = "test-password-123"
        key1, salt1 = ConfigCrypto.derive_key(password)

        assert key1 is not None
        assert salt1 is not None
        assert len(salt1) == 16  # Salt size

        # Same password with same salt should produce same key
        key2, _ = ConfigCrypto.derive_key(password, salt1)
        assert key1 == key2

    def test_encrypt_decrypt_field(self):
        """Test encrypting and decrypting a single field."""
        crypto = ConfigCrypto(ConfigCrypto.generate_key())

        original = "https://github.company.com/api/v3"
        encrypted = crypto.encrypt_field(original)

        # Verify encryption
        assert encrypted.startswith("ENC:")
        assert encrypted != original

        # Verify decryption
        decrypted = crypto.decrypt_field(encrypted)
        assert decrypted == original

    def test_is_encrypted(self):
        """Test encryption detection."""
        crypto = ConfigCrypto(ConfigCrypto.generate_key())

        plain_text = "not encrypted"
        encrypted_text = crypto.encrypt_field("test")

        assert not crypto.is_encrypted(plain_text)
        assert crypto.is_encrypted(encrypted_text)

    def test_encrypt_selective(self):
        """Test selective field encryption."""
        crypto = ConfigCrypto(ConfigCrypto.generate_key())

        config = {
            "github": {
                "api_url": "https://github.company.com",
                "owner": "company-org",
                "timeout": 30,
            },
            "branch": {
                "pattern": "^feature/.*",
            },
        }

        fields_to_encrypt = ["github.api_url", "github.owner"]
        encrypted_config = crypto.encrypt_selective(config, fields_to_encrypt)

        # Check encrypted fields
        assert crypto.is_encrypted(encrypted_config["github"]["api_url"])
        assert crypto.is_encrypted(encrypted_config["github"]["owner"])

        # Check non-encrypted fields
        assert encrypted_config["github"]["timeout"] == 30
        assert encrypted_config["branch"]["pattern"] == "^feature/.*"

    def test_decrypt_selective(self):
        """Test selective field decryption."""
        crypto = ConfigCrypto(ConfigCrypto.generate_key())

        config = {
            "github": {
                "api_url": "https://github.company.com",
                "owner": "company-org",
                "timeout": 30,
            },
        }

        # Encrypt
        encrypted_config = crypto.encrypt_selective(config, ["github.api_url", "github.owner"])

        # Decrypt
        decrypted_config = crypto.decrypt_selective(encrypted_config)

        # Verify decryption
        assert decrypted_config["github"]["api_url"] == "https://github.company.com"
        assert decrypted_config["github"]["owner"] == "company-org"
        assert decrypted_config["github"]["timeout"] == 30

    def test_encrypt_without_key_raises_error(self):
        """Test that encryption without key raises error."""
        crypto = ConfigCrypto(key=None)

        with pytest.raises(ValueError, match="Encryption key not set"):
            crypto.encrypt_field("test")

    def test_decrypt_without_key_raises_error(self):
        """Test that decryption without key raises error."""
        crypto = ConfigCrypto(key=None)

        with pytest.raises(ValueError, match="Encryption key not set"):
            crypto.decrypt_field("ENC:test")

    def test_decrypt_non_encrypted_value_raises_error(self):
        """Test that decrypting non-encrypted value raises error."""
        crypto = ConfigCrypto(ConfigCrypto.generate_key())

        with pytest.raises(ValueError, match="does not have ENC: prefix"):
            crypto.decrypt_field("not-encrypted")

    def test_roundtrip_encryption(self):
        """Test complete encryption/decryption roundtrip."""
        key = ConfigCrypto.generate_key()
        crypto = ConfigCrypto(key)

        test_values = [
            "simple-string",
            "https://api.example.com/v1",
            "company-org-name",
            "special-chars-!@#$%^&*()",
            "unicode-テスト-🔒",
        ]

        for value in test_values:
            encrypted = crypto.encrypt_field(value)
            decrypted = crypto.decrypt_field(encrypted)
            assert decrypted == value, f"Roundtrip failed for: {value}"

    def test_save_and_load_key(self, tmp_path):
        """Test saving and loading encryption key."""
        key = ConfigCrypto.generate_key()
        crypto = ConfigCrypto(key)

        key_file = tmp_path / "test.key"
        crypto.save_key(str(key_file))

        # Load key
        loaded_key = ConfigCrypto.load_key(str(key_file))
        assert loaded_key == key

        # Verify loaded key works
        crypto2 = ConfigCrypto(loaded_key)
        original = "test-value"
        encrypted = crypto.encrypt_field(original)
        decrypted = crypto2.decrypt_field(encrypted)
        assert decrypted == original
