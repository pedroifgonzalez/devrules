"""Project cache management for GitHub Projects metadata.

Stores and retrieves metadata needed for fast project operations.
"""

import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional


@dataclass
class ProjectCacheEntry:
    owner: str
    project_number: str
    project_id: Optional[str] = None
    fields: Optional[list[dict[str, Any]]] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class ProjectCacheManager:
    """Manages project metadata cache storage and retrieval."""

    def __init__(self, storage_path: Optional[str] = None, max_entries: int = 200):
        if storage_path is None:
            storage_path = os.path.expanduser("~/.devrules/project_cache.json")
        else:
            storage_path = os.path.expanduser(storage_path)

        self.storage_path = Path(storage_path)
        self.max_entries = max_entries
        self._ensure_storage_dir()

    def _ensure_storage_dir(self) -> None:
        """Ensure storage folder exists"""
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

    def _cache_key(self, owner: str, project_number: str) -> str:
        """Generate cache key for project"""
        return f"{owner}/{project_number}"

    def _load_cache(self) -> dict[str, dict[str, Any]]:
        """Load cache from storage"""
        if not self.storage_path.exists():
            return {}

        try:
            with open(self.storage_path, "r") as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
        except (json.JSONDecodeError, IOError):
            return {}

    def _save_cache(self, cache: dict[str, dict[str, Any]]) -> None:
        """Save cache to storage"""
        try:
            with open(self.storage_path, "w") as f:
                json.dump(cache, f, indent=2)
        except IOError:
            pass

    def get_project_id(self, owner: str, project_number: str) -> Optional[str]:
        """Get project ID from cache"""
        cache = self._load_cache()
        entry = cache.get(self._cache_key(owner, project_number)) or {}
        value = entry.get("project_id")
        return str(value) if value else None

    def set_project_id(self, owner: str, project_number: str, project_id: str) -> None:
        """Set project ID in cache"""
        if not project_id:
            return
        cache = self._load_cache()
        key = self._cache_key(owner, project_number)
        entry = cache.get(key) or {}
        entry["owner"] = owner
        entry["project_number"] = project_number
        entry["project_id"] = project_id
        entry["timestamp"] = datetime.now().isoformat()
        cache[key] = entry
        self._trim_and_save(cache)

    def get_fields(self, owner: str, project_number: str) -> Optional[list[dict[str, Any]]]:
        """Get fields from cache"""
        cache = self._load_cache()
        entry = cache.get(self._cache_key(owner, project_number)) or {}
        fields = entry.get("fields")
        return fields if isinstance(fields, list) else None

    def set_fields(self, owner: str, project_number: str, fields: list[dict[str, Any]]) -> None:
        """Set fields in cache"""
        if not fields:
            return
        cache = self._load_cache()
        key = self._cache_key(owner, project_number)
        entry = cache.get(key) or {}
        entry["owner"] = owner
        entry["project_number"] = project_number
        entry["fields"] = fields
        entry["timestamp"] = datetime.now().isoformat()
        cache[key] = entry
        self._trim_and_save(cache)

    def _trim_and_save(self, cache: dict[str, dict[str, Any]]) -> None:
        """Trim cache to max entries and save"""
        if len(cache) <= self.max_entries:
            self._save_cache(cache)
            return

        def ts(v: dict[str, Any]) -> str:
            return str(v.get("timestamp") or "")

        items = sorted(cache.items(), key=lambda kv: ts(kv[1]), reverse=True)
        trimmed = dict(items[: self.max_entries])
        self._save_cache(trimmed)


_global_project_cache_manager: Optional[ProjectCacheManager] = None


def get_project_cache_manager(storage_path: Optional[str] = None) -> ProjectCacheManager:
    """Get global project cache manager"""
    global _global_project_cache_manager
    if _global_project_cache_manager is None:
        _global_project_cache_manager = ProjectCacheManager(storage_path=storage_path)
    return _global_project_cache_manager
