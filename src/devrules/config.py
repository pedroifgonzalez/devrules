"""Configuration management for DevRules."""

from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

import toml
import typer

from devrules.adapters.prompters.factory import get_default_prompter
from devrules.notifications import configure
from devrules.notifications.channels.slack import SlackChannel, resolve_slack_channel
from devrules.notifications.dispatcher import NotificationDispatcher

prompter = get_default_prompter()


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
    enable_ai_suggestions: bool = False
    auto_push: bool = False


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
    prefixes_tags: dict = field(default_factory=dict)


@dataclass
class GitHubConfig:
    """GitHub API configuration."""

    api_url: str = "https://api.github.com"
    timeout: int = 30
    owner: Optional[str] = None
    repo: Optional[str] = None
    token: Optional[str] = None
    projects: dict = field(default_factory=dict)
    valid_statuses: list = field(default_factory=list)
    integration_comment_status: str = "Waiting Integration"
    require_evidence_status: Optional[str] = None
    status_emojis: dict = field(default_factory=dict)
    project_cache_enabled: bool = False
    project_cache_path: Optional[str] = None
    excluded_work_statuses: list = field(default_factory=lambda: ["Blocked", "Waiting Integration"])
    start_work_status: str = "In Progress"
    recent_comments_hours: int = 24
    priorities_hierarchy: list = field(default_factory=lambda: ["High", "Medium", "Low"])
    labels_priorities_hierarchy: list = field(default_factory=lambda: ["P1", "P2", "P3"])

    def _validate(self):
        """Validate the configuration."""
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
        if (
            self.require_evidence_status
            and self.valid_statuses
            and self.require_evidence_status not in self.valid_statuses
        ):
            typer.secho(
                f"Invalid evidence status: {self.require_evidence_status}",
                fg=typer.colors.RED,
            )
            raise typer.Exit(code=1)


@dataclass
class JiraConfig:
    """Jira API configuration."""

    url: str = ""
    email: Optional[str] = None
    api_token: Optional[str] = None
    default_project: Optional[str] = None
    timeout: int = 30

    def is_configured(self) -> bool:
        """Return whether Jira credentials are configured."""
        return bool(self.url and self.email and self.api_token)

    def _validate(self) -> None:
        """Validate Jira configuration required for Jira commands."""
        missing_fields = []
        if not self.url:
            missing_fields.append("jira.url")
        if not self.email:
            missing_fields.append("jira.email")
        if not self.api_token:
            missing_fields.append("jira.api_token")

        if missing_fields:
            typer.secho(
                "✘ Jira is not fully configured. Missing: " + ", ".join(missing_fields),
                fg=typer.colors.RED,
            )
            raise typer.Exit(code=1)


@dataclass
class EnvironmentConfig:
    """Configuration for a deployment environment."""

    name: str
    default_branch: str
    jenkins_job_name: Optional[str] = None  # If None, uses repo name from github.repo
    pattern: Optional[str] = None
    transition_status: Optional[str] = (
        None  # Status to transition the current issue detected by branch
    )


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
class SlackChannelConfig:
    """Configuration for Slack notifications."""

    enabled: bool = False
    token: str = ""
    channels: dict = field(default_factory=dict)  # event type → channel name


@dataclass
class ChannelConfig:
    """Configuration for notification channels."""

    slack: SlackChannelConfig = field(default_factory=SlackChannelConfig)


@dataclass
class RoleConfig:
    """Configuration for a role's permissions."""

    allowed_statuses: list = field(default_factory=list)  # Statuses this role can transition to
    deployable_environments: list = field(
        default_factory=list
    )  # Environments this role can deploy to


@dataclass
class PermissionsConfig:
    """Role-based permissions configuration."""

    roles: Dict[str, RoleConfig] = field(default_factory=dict)
    default_role: Optional[str] = None  # Fallback role when user not assigned
    user_assignments: Dict[str, str] = field(default_factory=dict)  # username → role_name


@dataclass
class LoggingConfig:
    """Logging configuration."""

    enabled: bool = False
    level: str = "WARNING"
    format: Optional[str] = None


@dataclass
class CustomRulesConfig:
    """Configuration for custom validation rules."""

    paths: list = field(default_factory=list)
    packages: list = field(default_factory=list)


@dataclass
class Config:
    """Main configuration container."""

    branch: BranchConfig
    commit: CommitConfig
    pr: PRConfig
    github: GitHubConfig = field(default_factory=GitHubConfig)
    jira: JiraConfig = field(default_factory=JiraConfig)
    deployment: DeploymentConfig = field(default_factory=DeploymentConfig)
    validation: ValidationConfig = field(default_factory=ValidationConfig)
    documentation: DocumentationConfig = field(default_factory=DocumentationConfig)
    functional_groups: Dict[str, FunctionalGroupConfig] = field(default_factory=dict)
    channel: ChannelConfig = field(default_factory=ChannelConfig)
    permissions: PermissionsConfig = field(default_factory=PermissionsConfig)
    custom_rules: CustomRulesConfig = field(default_factory=CustomRulesConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)


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
        "enable_ai_suggestions": False,
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
        "require_evidence_status": "Tech Lead Review",
        "valid_statuses": [
            "Backlog",
            "Blocked",
            "To Do",
            "In Progress",
            "Waiting Integration",
            "Tech Lead Review",
            "QA Testing",
            "QA In Progress",
            "QA Approved",
            "Pending To Deploy",
            "Done",
        ],
        "status_emojis": {},
        "project_cache_enabled": False,
        "project_cache_path": None,
        "excluded_work_statuses": ["Blocked", "Waiting Integration"],
        "start_work_status": "In Progress",
        "recent_comments_hours": 24,
    },
    "jira": {
        "url": "",
        "email": None,
        "api_token": None,
        "default_project": None,
        "timeout": 30,
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
    "permissions": {
        "roles": {},
        "default_role": None,
        "user_assignments": {},
    },
    "custom_rules": {
        "paths": [],
        "packages": [],
    },
    "logging": {
        "enabled": False,
        "level": "WARNING",
        "format": None,
    },
}


def find_config_file() -> Optional[Path]:
    """Search for config file in current directory and parent directories."""
    current = Path.cwd()

    config_names = [".devrules.toml", "devrules.toml"]

    for parent in [current] + list(current.parents):
        for name in config_names:
            config_path = parent / name
            if config_path.exists():
                return config_path

    return None


def load_config(config_path: Optional[Path] = None) -> Config:
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
                prompter.warning("Enterprise configuration integrity check failed!")
                prompter.warning("The configuration may have been tampered with.")

            # Load enterprise config
            enterprise_config_data = enterprise_mgr.load_enterprise_config()
            is_locked = enterprise_mgr.is_locked()

            if enterprise_config_data and is_locked:
                prompter.info("Enterprise mode: Using locked corporate configuration")
    except ImportError:
        # Enterprise module not available
        pass
    except Exception as e:
        prompter.error(f"Error loading enterprise config: {e}")
        prompter.exit(code=1)

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
            prompter.error(f"Error loading user config file:\n{e}")
            prompter.exit(code=1)

    # Merge configurations with priority
    config_data: Dict[str, Any] = deepcopy(DEFAULT_CONFIG)

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
    validated_jira_config = JiraConfig(**config_data.get("jira", {}))

    # Parse channel / notification config
    channel_data = config_data.get("channel", {})
    slack_data = channel_data.get("slack", {})

    slack_config = SlackChannelConfig(
        enabled=slack_data.get("enabled", False),
        token=slack_data.get("token", ""),
        channels=slack_data.get("channels", {}),
    )

    channel_config = ChannelConfig(slack=slack_config)

    if channel_config.slack.enabled:
        slack_channel = SlackChannel(
            token=channel_config.slack.token,
            channel_resolver=resolve_slack_channel,
            channels_map=channel_config.slack.channels,
        )
        configure(NotificationDispatcher(channels=[slack_channel]))

    # Parse permissions config
    permissions_data = config_data.get("permissions", {})
    roles_dict = {}
    for role_name, role_data in permissions_data.get("roles", {}).items():
        if isinstance(role_data, dict):
            roles_dict[role_name] = RoleConfig(**role_data)

    permissions_config = PermissionsConfig(
        roles=roles_dict,
        default_role=permissions_data.get("default_role"),
        user_assignments=permissions_data.get("user_assignments", {}),
    )

    # Parse custom rules config
    custom_rules_data = config_data.get("custom_rules", {})
    custom_rules_config = CustomRulesConfig(
        paths=custom_rules_data.get("paths", []),
        packages=custom_rules_data.get("packages", []),
    )

    # Parse logging config
    logging_data = config_data.get("logging", {})
    logging_config = LoggingConfig(**logging_data)

    return Config(
        branch=BranchConfig(**config_data["branch"]),
        commit=CommitConfig(**{**config_data["commit"], "pattern": commit_pattern}),
        pr=PRConfig(**{**config_data["pr"], "title_pattern": pr_pattern}),
        github=validated_github_config,
        jira=validated_jira_config,
        deployment=deployment_config,
        validation=ValidationConfig(**config_data.get("validation", {})),
        documentation=documentation_config,
        functional_groups=functional_groups_dict,
        channel=channel_config,
        permissions=permissions_config,
        custom_rules=custom_rules_config,
        logging=logging_config,
    )
