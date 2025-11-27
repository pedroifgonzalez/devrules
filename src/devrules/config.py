"""Configuration management for DevRules."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

import toml


@dataclass
class BranchConfig:
    """Branch validation configuration."""

    pattern: str
    prefixes: list
    require_issue_number: bool = False
    enforce_single_branch_per_issue_env: bool = True
    labels_mapping: dict = field(default_factory=dict)
    labels_hierarchy: list = field(default_factory=list)


@dataclass
class CommitConfig:
    """Commit message validation configuration."""

    tags: list
    pattern: str
    min_length: int = 10
    max_length: int = 100
    restrict_branch_to_owner: bool = False
    append_issue_number: bool = True
    allow_hook_bypass: bool = False


@dataclass
class PRConfig:
    """Pull Request validation configuration."""

    max_loc: int = 400
    max_files: int = 20
    require_title_tag: bool = True
    title_pattern: str = ""


@dataclass
class GitHubConfig:
    """GitHub API configuration."""

    api_url: str = "https://api.github.com"
    timeout: int = 30
    owner: Optional[str] = None
    repo: Optional[str] = None
    projects: dict = field(default_factory=dict)
    valid_statuses: list = field(default_factory=list)
    status_emojis: dict = field(default_factory=dict)


@dataclass
class Config:
    """Main configuration container."""

    branch: BranchConfig
    commit: CommitConfig
    pr: PRConfig
    github: GitHubConfig = field(default_factory=GitHubConfig)


DEFAULT_CONFIG = {
    "branch": {
        "pattern": r"^(feature|bugfix|hotfix|release|docs)/(\d+-)?[a-z0-9-]+",
        "prefixes": ["feature", "bugfix", "hotfix", "release", "docs"],
        "require_issue_number": False,
        "enforce_single_branch_per_issue_env": True,
        "labels_mapping": {"enhancement": "feature", "bug": "bugfix", "documentation": "docs"},
        "labels_hierarchy": ["docs", "feature", "bugfix", "hotfix"],
    },
    "commit": {
        "tags": [
            "WIP",
            "FTR",
            "SCR",
            "CLP",
            "CRO",
            "TST",
            "!!!",
            "FIX",
            "RFR",
            "ADD",
            "REM",
            "REV",
            "MOV",
            "REL",
            "IMP",
            "MERGE",
            "I18N",
            "DOCS",
        ],
        "pattern": r"^\[({tags})\].+",
        "min_length": 10,
        "max_length": 100,
        "append_issue_number": True,
        "allow_hook_bypass": False,
    },
    "pr": {
        "max_loc": 400,
        "max_files": 20,
        "require_title_tag": True,
        "title_pattern": r"^\[({tags})\].+",
    },
    "github": {
        "api_url": "https://api.github.com",
        "timeout": 30,
        "owner": None,
        "repo": None,
        "projects": {},
        "valid_statuses": [
            "Backlog",
            "Blocked",
            "To Do",
            "In Progress",
            "Waiting Integration",
            "QA Testing",
            "QA In Progress",
            "QA Approved",
            "Pending To Deploy",
            "Done",
        ],
        "status_emojis": {},
    },
}


def find_config_file() -> Optional[Path]:
    """Search for config file in current directory and parent directories."""
    current = Path.cwd()

    config_names = [".devrules.toml", "devrules.toml", ".devrules"]

    for parent in [current] + list(current.parents):
        for name in config_names:
            config_path = parent / name
            if config_path.exists():
                return config_path

    return None


def load_config(config_path: Optional[str] = None) -> Config:
    """Load configuration from TOML file or use defaults."""

    path: Optional[Path]
    if config_path:
        path = Path(config_path)
    else:
        path = find_config_file()

    config_data: Dict[str, Any]
    if path is not None and path.exists():
        try:
            user_config = toml.load(path)
            config_data = {**DEFAULT_CONFIG}

            # Deep merge
            for section in user_config:
                if section in config_data:
                    config_data[section].update(user_config[section])
                else:
                    config_data[section] = user_config[section]
        except Exception as e:
            print(f"Warning: Error loading config file: {e}")
            config_data = DEFAULT_CONFIG
    else:
        config_data = DEFAULT_CONFIG

    # Build pattern with tags
    raw_tags = config_data["commit"]["tags"]
    tags_list = [str(tag) for tag in raw_tags]
    tags_str = "|".join(tags_list)

    commit_pattern_base = str(config_data["commit"]["pattern"])
    commit_pattern = commit_pattern_base.replace("{tags}", tags_str)

    pr_pattern_base = str(config_data["pr"]["title_pattern"])
    pr_pattern = pr_pattern_base.replace("{tags}", tags_str)

    return Config(
        branch=BranchConfig(**config_data["branch"]),
        commit=CommitConfig(**{**config_data["commit"], "pattern": commit_pattern}),
        pr=PRConfig(**{**config_data["pr"], "title_pattern": pr_pattern}),
        github=GitHubConfig(**config_data.get("github", {})),
    )
