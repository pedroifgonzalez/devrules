import os
import subprocess
from typing import Any, Callable, Dict

import typer


def _install_commit_msg_hook(hooks_dir: str, devrules_path: str) -> None:
    """Install commit-msg hook to validate commit messages."""
    commit_msg_hook = os.path.join(hooks_dir, "commit-msg")

    commit_msg_content = f"""#!/bin/sh
# DevRules commit-msg hook
# Validates commit message format, then runs pre-commit if available

# Step 1: Run devrules validation
"{devrules_path}" check-commit "$1"
DEVRULES_EXIT=$?

if [ $DEVRULES_EXIT -ne 0 ]; then
    exit $DEVRULES_EXIT
fi

# Step 2: Run pre-commit commit-msg hooks if pre-commit is installed
if command -v pre-commit >/dev/null 2>&1; then
    if [ -f .pre-commit-config.yaml ]; then
        pre-commit hook-impl --config=.pre-commit-config.yaml --hook-type=commit-msg --hook-dir="$GIT_DIR/hooks" -- "$@"
        exit $?
    fi
fi

exit 0
"""

    _write_hook_file(commit_msg_hook, commit_msg_content, "commit-msg")


def _install_pre_commit_hook(hooks_dir: str, devrules_path: str) -> None:
    """Install pre-commit hook to validate files before commit."""
    pre_commit_hook = os.path.join(hooks_dir, "pre-commit")

    pre_commit_content = f"""#!/bin/sh
# DevRules pre-commit hook
# Validates files and repository state before commit

# Run devrules pre-commit validation
"{devrules_path}" pre-commit-check
DEVRULES_EXIT=$?

if [ $DEVRULES_EXIT -ne 0 ]; then
    exit $DEVRULES_EXIT
fi

# Run pre-commit hooks if pre-commit is installed
if command -v pre-commit >/dev/null 2>&1; then
    if [ -f .pre-commit-config.yaml ]; then
        pre-commit run --all-files
        exit $?
    fi
fi

exit 0
"""

    _write_hook_file(pre_commit_hook, pre_commit_content, "pre-commit")


def _install_pre_push_hook(hooks_dir: str, devrules_path: str) -> None:
    """Install pre-push hook to validate branch before push."""
    pre_push_hook = os.path.join(hooks_dir, "pre-push")

    pre_push_content = f"""#!/bin/sh
# DevRules pre-push hook
# Validates branch and issue status before push

# Get current branch
current_branch=$(git symbolic-ref --short HEAD)

# Run devrules pre-push validation
"{devrules_path}" pre-push-check --branch "$current_branch"
DEVRULES_EXIT=$?

if [ $DEVRULES_EXIT -ne 0 ]; then
    exit $DEVRULES_EXIT
fi

exit 0
"""

    _write_hook_file(pre_push_hook, pre_push_content, "pre-push")


def _install_post_checkout_hook(hooks_dir: str, devrules_path: str) -> None:
    """Install post-checkout hook to show branch context."""
    post_checkout_hook = os.path.join(hooks_dir, "post-checkout")

    post_checkout_content = f"""#!/bin/sh
# DevRules post-checkout hook
# Shows branch context after checkout

# Only run for branch checkouts (not file checkouts)
if [ "$3" = "1" ]; then
    # Get current branch
    current_branch=$(git symbolic-ref --short HEAD 2>/dev/null || echo "HEAD")
    
    # Run devrules branch context
    "{devrules_path}" branch-context --branch "$current_branch" 2>/dev/null || true
fi

exit 0
"""

    _write_hook_file(post_checkout_hook, post_checkout_content, "post-checkout")


def _write_hook_file(hook_path: str, content: str, hook_name: str) -> None:
    """Write hook file with proper permissions."""
    if os.path.exists(hook_path):
        overwrite = typer.confirm(f"{hook_name} hook already exists. Overwrite?")
        if not overwrite:
            typer.echo(f"Skipping {hook_name} hook.")
            return
        typer.secho(f"✔ Updated: {hook_path}", fg=typer.colors.GREEN)
    else:
        typer.secho(f"✔ Created: {hook_path}", fg=typer.colors.GREEN)

    with open(hook_path, "w") as f:
        f.write(content)
    os.chmod(hook_path, 0o755)


def register(app: typer.Typer) -> Dict[str, Callable[..., Any]]:
    @app.command()
    def init_config(
        path: str = typer.Option(".devrules.toml", "--path", "-p", help="Config file path"),
    ):
        """Generate example configuration file."""

        github_owner = "your-github-username"
        github_repo = "your-repo-name"
        project = "Example Project (#6)"

        try:
            result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                capture_output=True,
                text=True,
                check=True,
            )
            url = result.stdout.strip()

            if "github.com" in url:
                if url.startswith("git@"):
                    path_part = url.split(":", 1)[1]
                else:
                    path_part = url.split("github.com", 1)[1].lstrip("/:")

                path_part = path_part.replace(".git", "")
                parts = path_part.split("/")

                if len(parts) >= 2:
                    github_owner = parts[-2]
                    github_repo = parts[-1]
        except Exception:
            pass

        example_config = r"""# DevRules Configuration File

[branch]
pattern = "^(feature|bugfix|hotfix|release|docs)/(\\d+-)?[a-z0-9-]+"
prefixes = ["feature", "bugfix", "hotfix", "release", "docs"]
require_issue_number = false
enforce_single_branch_per_issue_env = true  # If true, only one branch per issue per environment (dev/staging)
forbid_cross_repo_cards = false  # If true, prevents creating branches from cards/issues belonging to other repositories
labels_hierarchy = ["docs", "feature", "bugfix", "hotfix"]

[branch.labels_mapping]
enhancement = "feature"
bug = "bugfix"
documentation = "docs"

[commit]
tags = ["WIP", "FTR", "FIX", "DOCS", "TST", "REF"]
pattern = "^\\\[({tags})\\\].+"
min_length = 10
max_length = 100
restrict_branch_to_owner = true
append_issue_number = true
allow_hook_bypass = false  # If true, allows commits with --no-verify flag
gpg_sign = false  # If true, signs commits with GPG (requires git config user.signingkey)
protected_branch_prefixes = ["staging-"]  # Branches that should not receive direct commits (merge-only)
# Forbidden file patterns (glob patterns)
forbidden_patterns = ["*.dump", "*.sql", ".env.local", "*.log", "*.swp", "*~"]
# Forbidden paths (directories that should not be committed)
forbidden_paths = ["tmp/", "cache/", "local/"]

[pr]
max_loc = 400
max_files = 20
require_title_tag = true
title_pattern = "^\\\[({tags})\\\].+"
# Enable issue status validation before PR creation (default: false)
require_issue_status_check = false
# List of statuses that allow PR creation (e.g., ["In review", "Ready"])
allowed_pr_statuses = []
# List of project keys from [github.projects] to check status against
# If empty, checks all configured projects
project_for_status_check = []
# Allowed target branches for PRs (if empty, no restriction)
allowed_targets = ["develop", "main", "staging"]

[github]
api_url = "https://api.github.com"
timeout = 30
owner = "{github_owner}"  # GitHub repository owner
repo = "{github_repo}"          # GitHub repository name
valid_statuses = [
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
]

[github.status_emojis]
# Emoji mappings for issue statuses (used in list_issues output)
# backlog = "📋"
# in_progress = "🔄"
# done = "✅"

[github.projects]
project = "{project}"

[deployment]
# Jenkins configuration for deployments
jenkins_url = "https://jenkins.yourcompany.com"
# jenkins_user = "your-username"  # Can also use env var JENKINS_USER
# jenkins_token = "your-api-token"  # Can also use env var JENKINS_TOKEN
multibranch_pipeline = false  # If true, uses /job/{{name}}/job/{{branch}} URL format
migration_detection_enabled = true
migration_paths = ["migrations/", "alembic/versions/"]
auto_rollback_on_failure = true
require_confirmation = true

[deployment.environments.dev]
name = "dev"
default_branch = "develop"
# jenkins_job_name = "deploy-backend-dev"  # Optional: defaults to github.repo

[deployment.environments.staging]
name = "staging"
default_branch = "staging"

[deployment.environments.prod]
name = "prod"
default_branch = "main"

[validation]
# Check for uncommitted changes before branch creation
check_uncommitted = true
# Check if local branch is behind remote before branch creation
check_behind_remote = true
# If true, show warnings but don't block operations
warn_only = false
# Allowed base branches for creating new branches (empty = no restriction)
allowed_base_branches = []
# Forbidden base branch patterns (regex patterns)
forbidden_base_patterns = []

[documentation]
# Show context-aware documentation during commits
show_on_commit = true
# Show context-aware documentation during PR creation
show_on_pr = true

# Documentation rules - show relevant docs based on files changed
# Uncomment and customize these examples:
# [[documentation.rules]]
# file_pattern = "migrations/**"
# docs_url = "https://wiki.company.com/database-migrations"
# message = "You're modifying migrations. Please review the migration guidelines."
# checklist = [
#   "Update the entrypoint if adding new tables",
#   "Test the migration rollback",
#   "Update the database schema documentation"
# ]

# [[documentation.rules]]
# file_pattern = "api/**/*.py"
# docs_url = "https://wiki.company.com/api-guidelines"
# message = "API changes detected"
# checklist = [
#   "Update API documentation",
#   "Add/update tests",
#   "Consider backward compatibility"
# ]
""".format(
            github_owner=github_owner,
            github_repo=github_repo,
            project=project,
            tags="WIP|FTR|FIX|DOCS|TST|REF",
        )

        if os.path.exists(path):
            overwrite = typer.confirm(f"{path} already exists. Overwrite?")
            if not overwrite:
                typer.echo("Cancelled.")
                raise typer.Exit(code=0)

        with open(path, "w") as f:
            f.write(example_config)

        typer.secho(f"✔ Configuration file created: {path}", fg=typer.colors.GREEN)

    @app.command()
    def install_hooks():
        """Install git hooks to enforce devrules validation on commits and pushes."""
        hooks_dir = ".git/hooks"

        if not os.path.exists(".git"):
            typer.secho("✘ Not a git repository. Run 'git init' first.", fg=typer.colors.RED)
            raise typer.Exit(code=1)

        os.makedirs(hooks_dir, exist_ok=True)

        # Get the path to the devrules executable
        import shutil

        devrules_path = shutil.which("devrules") or "devrules"

        # 1. Install commit-msg hook
        _install_commit_msg_hook(hooks_dir, devrules_path)

        # 2. Install pre-commit hook
        _install_pre_commit_hook(hooks_dir, devrules_path)

        # 3. Install pre-push hook
        _install_pre_push_hook(hooks_dir, devrules_path)

        # 4. Install post-checkout hook
        _install_post_checkout_hook(hooks_dir, devrules_path)

        typer.secho("\n✔ All git hooks installed!", fg=typer.colors.GREEN)
        typer.echo("  • Commit messages will be validated by devrules")
        typer.echo("  • Files will be checked before commits")
        typer.echo("  • Branches will be validated before pushes")
        typer.echo("  • Branch context will be shown on checkout")
        typer.echo("  Use 'git commit --no-verify' to bypass (if allowed by config).")

    @app.command()
    def uninstall_hooks():
        """Remove devrules git hooks."""
        hooks = [
            ".git/hooks/commit-msg",
            ".git/hooks/pre-commit",
            ".git/hooks/pre-push",
            ".git/hooks/post-checkout",
        ]

        for hook_path in hooks:
            if os.path.exists(hook_path):
                os.remove(hook_path)
                typer.secho(f"✔ Removed: {hook_path}", fg=typer.colors.GREEN)
            else:
                typer.echo(f"  {hook_path} not found, skipping.")

        typer.secho("\n✔ All git hooks uninstalled.", fg=typer.colors.GREEN)

    return {
        "init_config": init_config,
        "install_hooks": install_hooks,
        "uninstall_hooks": uninstall_hooks,
    }
