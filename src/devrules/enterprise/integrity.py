"""Integrity verification for enterprise configuration."""

import hashlib
import json
from typing import Any, Dict


class IntegrityVerifier:
    """Handles integrity verification of configuration files."""

    HASH_ALGORITHM = "sha256"

    @staticmethod
    def generate_hash(config: Dict[str, Any]) -> str:
        """Generate SHA-256 hash of configuration.

        Args:
            config: Configuration dictionary

        Returns:
            Hexadecimal hash string
        """
        # Convert to JSON with sorted keys for consistent hashing
        config_json = json.dumps(config, sort_keys=True, separators=(",", ":"))
        hash_obj = hashlib.sha256(config_json.encode())
        return hash_obj.hexdigest()

    @staticmethod
    def verify_hash(config: Dict[str, Any], expected_hash: str) -> bool:
        """Verify configuration hash.

        Args:
            config: Configuration dictionary
            expected_hash: Expected hash value

        Returns:
            True if hash matches, False otherwise
        """
        actual_hash = IntegrityVerifier.generate_hash(config)
        return actual_hash == expected_hash

    @staticmethod
    def create_integrity_file(config: Dict[str, Any], filepath: str) -> None:
        """Create integrity hash file.

        Args:
            config: Configuration dictionary
            filepath: Path to save hash file
        """
        hash_value = IntegrityVerifier.generate_hash(config)
        with open(filepath, "w") as f:
            f.write(hash_value)

    @staticmethod
    def load_integrity_file(filepath: str) -> str:
        """Load integrity hash from file.

        Args:
            filepath: Path to hash file

        Returns:
            Hash value
        """
        with open(filepath, "r") as f:
            return f.read().strip()

    @staticmethod
    def verify_from_file(config: Dict[str, Any], hash_filepath: str) -> bool:
        """Verify configuration against hash file.

        Args:
            config: Configuration dictionary
            hash_filepath: Path to hash file

        Returns:
            True if hash matches, False otherwise
        """
        try:
            expected_hash = IntegrityVerifier.load_integrity_file(hash_filepath)
            return IntegrityVerifier.verify_hash(config, expected_hash)
        except FileNotFoundError:
            return False
