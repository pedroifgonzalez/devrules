"""Configuration management for DevRules."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

import toml
import typer


@dataclass
class BranchConfig:
    """Branch validation configuration."""

    pattern: str
    prefixes: list
    require_issue_number: bool = False
    enforce_single_branch_per_issue_env: bool = True
    labels_mapping: dict = field(default_factory=dict)
    labels_hierarchy: list = field(default_factory=list)
    forbid_cross_repo_cards: bool = False


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
    gpg_sign: bool = False
    protected_branch_prefixes: list = field(default_factory=list)
    forbidden_patterns: list = field(default_factory=list)
    forbidden_paths: list = field(default_factory=list)
    auto_stage: bool = False


@dataclass
class PRConfig:
    """Pull Request validation configuration."""

    max_loc: int = 400
    max_files: int = 20
    require_title_tag: bool = True
    title_pattern: str = ""
    require_issue_status_check: bool = False
    allowed_pr_statuses: list = field(default_factory=list)
    project_for_status_check: list = field(default_factory=list)
    allowed_targets: list = field(default_factory=list)
    target_rules: list = field(default_factory=list)
    auto_push: bool = False


@dataclass
class GitHubConfig:
    """GitHub API configuration."""

    api_url: str = "https://api.github.com"
    timeout: int = 30
    owner: Optional[str] = None
    repo: Optional[str] = None
    projects: dict = field(default_factory=dict)
    valid_statuses: list = field(default_factory=list)
    integration_comment_status: str = "Waiting Integration"
    status_emojis: dict = field(default_factory=dict)

    def _validate(self):
        if (
            self.integration_comment_status
            and self.valid_statuses
            and self.integration_comment_status not in self.valid_statuses
        ):
            typer.secho(
                f"Invalid integration comment status: {self.integration_comment_status}",
                fg=typer.colors.RED,
            )
            raise typer.Exit(code=1)


@dataclass
class EnvironmentConfig:
    """Configuration for a deployment environment."""

    name: str
    default_branch: str
    jenkins_job_name: Optional[str] = None  # If None, uses repo name from github.repo


@dataclass
class ValidationConfig:
    """Repository validation configuration."""

    check_uncommitted: bool = True
    check_behind_remote: bool = True
    warn_only: bool = False
    allowed_base_branches: list = field(default_factory=list)
    forbidden_base_patterns: list = field(default_factory=list)


@dataclass
class DocumentationRule:
    """Documentation rule for context-aware guidance."""

    file_pattern: str
    docs_url: str = ""
    checklist: list = field(default_factory=list)
    message: str = ""


@dataclass
class DocumentationConfig:
    """Documentation linking configuration."""

    rules: list = field(default_factory=list)
    show_on_commit: bool = True
    show_on_pr: bool = True


@dataclass
class IntegrationCursor:
    """The current integration point for a functional group."""

    branch: str
    environment: Optional[str] = None


@dataclass
class FunctionalGroupConfig:
    """Configuration for a functional group (Functional Feature)."""

    description: str = ""
    base_branch: str = "develop"
    branch_pattern: str = ""
    integration_cursor: Optional[IntegrationCursor] = None


@dataclass
class DeploymentConfig:
    """Deployment workflow configuration."""

    jenkins_url: str = ""
    jenkins_user: Optional[str] = None
    jenkins_token: Optional[str] = None
    multibranch_pipeline: bool = False  # If True, uses /job/{name}/job/{branch} URL format
    environments: dict = field(default_factory=dict)
    migration_detection_enabled: bool = True
    migration_paths: list = field(default_factory=lambda: ["migrations/", "alembic/versions/"])
    auto_rollback_on_failure: bool = True
    require_confirmation: bool = True


@dataclass
class Config:
    """Main configuration container."""

    branch: BranchConfig
    commit: CommitConfig
    pr: PRConfig
    github: GitHubConfig = field(default_factory=GitHubConfig)
    deployment: DeploymentConfig = field(default_factory=DeploymentConfig)
    validation: ValidationConfig = field(default_factory=ValidationConfig)
    documentation: DocumentationConfig = field(default_factory=DocumentationConfig)
    functional_groups: Dict[str, FunctionalGroupConfig] = field(default_factory=dict)


DEFAULT_CONFIG = {
    "branch": {
        "pattern": r"^(feature|bugfix|hotfix|release|docs)/(\d+-)?[a-z0-9-]+",
        "prefixes": ["feature", "bugfix", "hotfix", "release", "docs"],
        "require_issue_number": False,
        "enforce_single_branch_per_issue_env": True,
        "forbid_cross_repo_cards": False,
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
        "auto_stage": True,
    },
    "pr": {
        "max_loc": 400,
        "max_files": 20,
        "require_title_tag": True,
        "title_pattern": r"^\\[({tags})\\].+",
        "require_issue_status_check": False,
        "allowed_pr_statuses": [],
        "project_for_status_check": [],
        "auto_push": False,
    },
    "github": {
        "api_url": "https://api.github.com",
        "timeout": 30,
        "owner": None,
        "repo": None,
        "projects": {},
        "integration_comment_status": "Waiting Integration",
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
    "deployment": {
        "jenkins_url": "",
        "jenkins_user": None,
        "jenkins_token": None,
        "multibranch_pipeline": False,
        "environments": {},
        "migration_detection_enabled": True,
        "migration_paths": ["migrations/", "alembic/versions/"],
        "auto_rollback_on_failure": True,
        "require_confirmation": True,
    },
    "validation": {
        "check_uncommitted": True,
        "check_behind_remote": True,
        "warn_only": False,
        "allowed_base_branches": [],
        "forbidden_base_patterns": [],
    },
    "documentation": {
        "rules": [],
        "show_on_commit": True,
        "show_on_pr": True,
    },
    "functional_groups": {},
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
    """Load configuration from TOML file or use defaults.

    Configuration priority (highest to lowest):
    1. ENTERPRISE - Embedded enterprise config (if present and locked)
    2. USER - User's .devrules.toml file
    3. DEFAULT - Built-in defaults
    """
    # Check for enterprise mode first
    enterprise_config_data: Optional[Dict[str, Any]] = None
    is_locked = False

    try:
        from devrules.enterprise.config import EnterpriseConfig, verify_enterprise_integrity

        enterprise_mgr = EnterpriseConfig()
        if enterprise_mgr.is_enterprise_mode():
            # Verify integrity
            if not verify_enterprise_integrity():
                print("⚠️  Warning: Enterprise configuration integrity check failed!")
                print("   The configuration may have been tampered with.")

            # Load enterprise config
            enterprise_config_data = enterprise_mgr.load_enterprise_config()
            is_locked = enterprise_mgr.is_locked()

            if enterprise_config_data and is_locked:
                print("🔒 Enterprise mode: Using locked corporate configuration")
    except ImportError:
        # Enterprise module not available
        pass
    except Exception as e:
        print(f"Warning: Error loading enterprise config: {e}")

    # Load user configuration
    path: Optional[Path]
    if config_path:
        path = Path(config_path)
    else:
        path = find_config_file()

    user_config_data: Optional[Dict[str, Any]] = None
    if path is not None and path.exists():
        try:
            user_config_data = toml.load(path)
        except Exception as e:
            print(f"Warning: Error loading user config file: {e}")

    # Merge configurations with priority
    config_data: Dict[str, Any] = {**DEFAULT_CONFIG}

    # Apply user config if not locked by enterprise
    if user_config_data and not is_locked:
        for section in user_config_data:
            if section in config_data:
                config_data[section].update(user_config_data[section])
            else:
                config_data[section] = user_config_data[section]

    # Apply enterprise config (highest priority)
    if enterprise_config_data:
        # Remove enterprise metadata section before merging
        enterprise_data = {k: v for k, v in enterprise_config_data.items() if k != "enterprise"}
        for section in enterprise_data:
            if section in config_data:
                config_data[section].update(enterprise_data[section])
            else:
                config_data[section] = enterprise_data[section]

    # Build pattern with tags
    raw_tags = config_data["commit"]["tags"]
    tags_list = [str(tag) for tag in raw_tags]
    tags_str = "|".join(tags_list)

    commit_pattern_base = str(config_data["commit"]["pattern"])
    commit_pattern = commit_pattern_base.replace("{tags}", tags_str)

    pr_pattern_base = str(config_data["pr"]["title_pattern"])
    pr_pattern = pr_pattern_base.replace("{tags}", tags_str)

    # Parse deployment environments
    deployment_data = config_data.get("deployment", {})
    environments_dict = {}
    for env_key, env_data in deployment_data.get("environments", {}).items():
        if isinstance(env_data, dict):
            environments_dict[env_key] = EnvironmentConfig(**env_data)

    deployment_config = DeploymentConfig(
        **{
            **deployment_data,
            "environments": environments_dict,
        }
    )

    # Parse documentation rules
    doc_data = config_data.get("documentation", {})
    doc_rules = []
    for rule in doc_data.get("rules", []):
        if isinstance(rule, dict):
            doc_rules.append(DocumentationRule(**rule))

    documentation_config = DocumentationConfig(
        rules=doc_rules,
        show_on_commit=doc_data.get("show_on_commit", True),
        show_on_pr=doc_data.get("show_on_pr", True),
    )

    # Parse functional groups
    functional_groups_data = config_data.get("functional_groups", {})
    functional_groups_dict = {}
    for group_name, group_data in functional_groups_data.items():
        if isinstance(group_data, dict):
            cursor_data = group_data.get("integration_cursor")
            cursor = None
            if cursor_data:
                cursor = IntegrationCursor(**cursor_data)

            # Remove cursor from group_data to avoid double passing
            group_args = {k: v for k, v in group_data.items() if k != "integration_cursor"}

            functional_groups_dict[group_name] = FunctionalGroupConfig(
                **group_args, integration_cursor=cursor
            )

    # validated configs
    validated_github_config = GitHubConfig(**config_data.get("github", {}))
    validated_github_config._validate()

    return Config(
        branch=BranchConfig(**config_data["branch"]),
        commit=CommitConfig(**{**config_data["commit"], "pattern": commit_pattern}),
        pr=PRConfig(**{**config_data["pr"], "title_pattern": pr_pattern}),
        github=validated_github_config,
        deployment=deployment_config,
        validation=ValidationConfig(**config_data.get("validation", {})),
        documentation=documentation_config,
        functional_groups=functional_groups_dict,
    )
