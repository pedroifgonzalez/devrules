"""Issue mapping management for branches, issues, and project keys.

Stores and retrieves mappings between GitHub issues, branches, and project keys
to improve user experience by automatically resolving contexts.
"""

import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class IssueMapping:
    """A mapping between an issue, branch, and project key."""

    issue_number: int
    branch_name: str
    project_key: str
    item_id: Optional[str] = None
    item_title: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class IssueMappingManager:
    """Manages issue-branch-project mappings storage and retrieval."""

    def __init__(self, storage_path: Optional[str] = None, max_entries: int = 100):
        """Initialize issue mapping manager.

        Args:
            storage_path: Path to mappings file (default: ~/.devrules/issue_mappings.json)
            max_entries: Maximum entries to keep
        """
        if storage_path is None:
            storage_path = os.path.expanduser("~/.devrules/issue_mappings.json")
        else:
            storage_path = os.path.expanduser(storage_path)

        self.storage_path = Path(storage_path)
        self.max_entries = max_entries
        self._ensure_storage_dir()

    def _ensure_storage_dir(self) -> None:
        """Ensure the storage directory exists."""
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

    def _load_mappings(self) -> list[dict]:
        """Load mappings from disk.

        Returns:
            List of mapping dictionaries
        """
        if not self.storage_path.exists():
            return []

        try:
            with open(self.storage_path, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            # If file is corrupted or unreadable, start fresh
            return []

    def _save_mappings(self, mappings: list[dict]) -> None:
        """Save mappings to disk.

        Args:
            mappings: List of mapping dictionaries
        """
        try:
            with open(self.storage_path, "w") as f:
                json.dump(mappings, f, indent=2)
        except IOError:
            # Silently fail if we can't write - don't break user's workflow
            pass

    def add_mapping(
        self,
        issue_number: int,
        branch_name: str,
        project_key: str,
        item_id: Optional[str] = None,
        item_title: Optional[str] = None,
    ) -> None:
        """Add a new issue-branch-project mapping.

        Args:
            issue_number: GitHub issue number
            branch_name: Branch name
            project_key: Project key from config
        """
        if not branch_name or not branch_name.strip():
            return

        branch_name = branch_name.strip()
        mappings = self._load_mappings()

        # Check if this exact mapping already exists
        existing_mapping = None
        for i, mapping in enumerate(mappings):
            if (
                mapping.get("issue_number") == issue_number
                and mapping.get("branch_name") == branch_name
                and mapping.get("project_key") == project_key
            ):
                existing_mapping = i
                break

        if existing_mapping is not None:
            # Update timestamp of existing mapping
            mappings[existing_mapping]["timestamp"] = datetime.now().isoformat()
            if item_id:
                mappings[existing_mapping]["item_id"] = item_id
            if item_title:
                mappings[existing_mapping]["item_title"] = item_title
        else:
            # Add new mapping at the front
            mappings.insert(
                0,
                {
                    "issue_number": issue_number,
                    "branch_name": branch_name,
                    "project_key": project_key,
                    "item_id": item_id,
                    "item_title": item_title,
                    "timestamp": datetime.now().isoformat(),
                },
            )

        # Trim to max entries
        mappings = mappings[: self.max_entries]

        self._save_mappings(mappings)

    def get_mapping_by_branch(self, branch_name: str) -> Optional[dict]:
        """Get mapping for a branch name.

        Args:
            branch_name: Branch name to search for

        Returns:
            Mapping dict with issue_number, branch_name, project_key, or None
        """
        mappings = self._load_mappings()

        for mapping in mappings:
            if mapping.get("branch_name") == branch_name:
                return mapping

        return None

    def get_mapping_by_issue(self, issue_number: int) -> Optional[dict]:
        """Get mapping for an issue number.

        Args:
            issue_number: Issue number to search for

        Returns:
            Mapping dict with issue_number, branch_name, project_key, or None
        """
        mappings = self._load_mappings()

        for mapping in mappings:
            if mapping.get("issue_number") == issue_number:
                return mapping

        return None

    def get_recent_mappings(self, limit: int = 10) -> list[dict]:
        """Get recent mappings.

        Args:
            limit: Maximum number of mappings to return

        Returns:
            List of recent mappings (most recent first)
        """
        mappings = self._load_mappings()
        return mappings[:limit]

    def remove_mapping(self, branch_name: str, issue_number: Optional[int] = None) -> bool:
        """Remove a mapping.

        Args:
            branch_name: Branch name of mapping to remove
            issue_number: Optional issue number to match (for safety)

        Returns:
            True if mapping was removed, False otherwise
        """
        mappings = self._load_mappings()
        original_length = len(mappings)

        if issue_number is not None:
            # Remove specific mapping
            mappings = [
                m
                for m in mappings
                if not (
                    m.get("branch_name") == branch_name and m.get("issue_number") == issue_number
                )
            ]
        else:
            # Remove all mappings for this branch
            mappings = [m for m in mappings if m.get("branch_name") != branch_name]

        if len(mappings) < original_length:
            self._save_mappings(mappings)
            return True

        return False

    def clear_all(self) -> None:
        """Clear all mappings."""
        self._save_mappings([])


# Global instance for easy access
_global_mapping_manager: Optional[IssueMappingManager] = None


def get_issue_mapping_manager() -> IssueMappingManager:
    """Get the global issue mapping manager instance.

    Returns:
        Global IssueMappingManager instance
    """
    global _global_mapping_manager
    if _global_mapping_manager is None:
        _global_mapping_manager = IssueMappingManager()
    return _global_mapping_manager
