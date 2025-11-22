"""Command-line interface for DevRules."""

import os
import subprocess
import json
import shutil
import re
import typer
from typing import Optional

from devrules.config import load_config
from devrules.validators.branch import validate_branch, validate_single_branch_per_issue_env
from devrules.validators.commit import validate_commit
from devrules.validators.pr import validate_pr, fetch_pr_info
from devrules.validators.ownership import validate_branch_ownership, list_user_owned_branches

app = typer.Typer(help="DevRules CLI — Enforce development guidelines.")


@app.command()
def check_branch(
    branch: str,
    config_file: Optional[str] = typer.Option(None, "--config", "-c", help="Path to config file"),
):
    """Validate branch naming convention."""
    config = load_config(config_file)
    is_valid, message = validate_branch(branch, config.branch)

    if is_valid:
        typer.secho(f"✔ {message}", fg=typer.colors.GREEN)
        raise typer.Exit(code=0)
    else:
        typer.secho(f"✘ {message}", fg=typer.colors.RED)
        raise typer.Exit(code=1)


@app.command()
def check_commit(
    file: str,
    config_file: Optional[str] = typer.Option(None, "--config", "-c", help="Path to config file"),
):
    """Validate commit message format."""
    config = load_config(config_file)

    if not os.path.exists(file):
        typer.secho(f"Commit message file not found: {file}", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    with open(file, "r") as f:
        message = f.read().strip()

    is_valid, result_message = validate_commit(message, config.commit)

    if is_valid:
        typer.secho(f"✔ {result_message}", fg=typer.colors.GREEN)
        raise typer.Exit(code=0)
    else:
        typer.secho(f"✘ {result_message}", fg=typer.colors.RED)
        raise typer.Exit(code=1)


@app.command()
def check_pr(
    pr_number: int,
    owner: Optional[str] = typer.Option(None, "--owner", "-o", help="GitHub repository owner"),
    repo: Optional[str] = typer.Option(None, "--repo", "-r", help="GitHub repository name"),
    config_file: Optional[str] = typer.Option(None, "--config", "-c", help="Path to config file"),
):
    """Validate PR size and title format."""
    config = load_config(config_file)

    # Use CLI arguments if provided, otherwise fall back to config
    github_owner = owner or config.github.owner
    github_repo = repo or config.github.repo

    if not github_owner or not github_repo:
        typer.secho(
            "✘ GitHub owner and repo must be provided via CLI arguments (--owner, --repo) "
            "or configured in the config file under [github] section.",
            fg=typer.colors.RED
        )
        raise typer.Exit(code=1)

    try:
        pr_info = fetch_pr_info(github_owner, github_repo, pr_number, config.github)
    except ValueError as e:
        typer.secho(f"✘ {str(e)}", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    except Exception as e:
        typer.secho(f"✘ Error fetching PR: {str(e)}", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    typer.echo(f"PR Title: {pr_info.title}")
    typer.echo(f"Total LOC: {pr_info.additions + pr_info.deletions}")
    typer.echo(f"Files changed: {pr_info.changed_files}")
    typer.echo("")

    is_valid, messages = validate_pr(pr_info, config.pr)

    for msg in messages:
        if "✔" in msg:
            typer.secho(msg, fg=typer.colors.GREEN)
        else:
            typer.secho(msg, fg=typer.colors.RED)

    raise typer.Exit(code=0 if is_valid else 1)


@app.command()
def init_config(
    path: str = typer.Option(".devrules.toml", "--path", "-p", help="Config file path")
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

    example_config = """# DevRules Configuration File

[branch]
pattern = "^(feature|bugfix|hotfix|release|docs)/(\\\\d+-)?[a-z0-9-]+"
prefixes = ["feature", "bugfix", "hotfix", "release", "docs"]
require_issue_number = false
enforce_single_branch_per_issue_env = true  # If true, only one branch per issue per environment (dev/staging)

[commit]
tags = ["WIP", "FTR", "FIX", "DOCS", "TST", "REF"]
pattern = "^\\\\[({tags})\\\\].+"
min_length = 10
max_length = 100
restrict_branch_to_owner = true
append_issue_number = true


[pr]
max_loc = 400
max_files = 20
require_title_tag = true
title_pattern = "^\\\\[({tags})\\\\].+"

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

[github.projects]
project = "{project}"
""".format(github_owner=github_owner, github_repo=github_repo, project=project, tags="WIP|FTR|FIX|DOCS|TST|REF")

    if os.path.exists(path):
        overwrite = typer.confirm(f"{path} already exists. Overwrite?")
        if not overwrite:
            typer.echo("Cancelled.")
            raise typer.Exit(code=0)

    with open(path, "w") as f:
        f.write(example_config)

    typer.secho(f"✔ Configuration file created: {path}", fg=typer.colors.GREEN)


@app.command()
def create_branch(
    config_file: Optional[str] = typer.Option(None, "--config", "-c", help="Path to config file"),
    branch_name: Optional[str] = typer.Argument(
        None, help="Branch name (if not provided, interactive mode)"
    ),
):
    """Create a new Git branch with validation (interactive mode)."""
    import subprocess
    import re

    config = load_config(config_file)

    # Check if in git repo
    try:
        subprocess.run(["git", "rev-parse", "--git-dir"], check=True, capture_output=True)
    except subprocess.CalledProcessError:
        typer.secho("✘ Not a git repository", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    # If branch name provided, use it directly
    if branch_name:
        final_branch_name = branch_name
    else:
        # Interactive mode
        typer.secho("\n🌿 Create New Branch", fg=typer.colors.CYAN, bold=True)
        typer.echo("=" * 50)

        # Step 1: Select branch type
        typer.echo("\n📋 Select branch type:")
        for idx, prefix in enumerate(config.branch.prefixes, 1):
            typer.echo(f"  {idx}. {prefix}")

        type_choice = typer.prompt("\nEnter number", type=int, default=1)

        if type_choice < 1 or type_choice > len(config.branch.prefixes):
            typer.secho("✘ Invalid choice", fg=typer.colors.RED)
            raise typer.Exit(code=1)

        branch_type = config.branch.prefixes[type_choice - 1]

        # Step 2: Issue/ticket number (optional)
        typer.echo("\n🔢 Issue/ticket number (optional):")
        issue_number = typer.prompt(
            "  Enter number or press Enter to skip", default="", show_default=False
        )

        # Step 3: Branch description
        typer.echo("\n📝 Branch description:")
        typer.echo("  Use lowercase and hyphens (e.g., 'fix-login-bug')")
        description = typer.prompt("  Description")

        # Clean and format description
        description = description.lower().strip()
        description = re.sub(r"[^a-z0-9-]", "-", description)
        description = re.sub(r"-+", "-", description)  # Remove multiple hyphens
        description = description.strip("-")  # Remove leading/trailing hyphens

        if not description:
            typer.secho("✘ Description cannot be empty", fg=typer.colors.RED)
            raise typer.Exit(code=1)

        # Build branch name
        if issue_number:
            final_branch_name = f"{branch_type}/{issue_number}-{description}"
        else:
            final_branch_name = f"{branch_type}/{description}"

    # Validate branch name
    typer.echo(f"\n🔍 Validating branch name: {final_branch_name}")
    is_valid, message = validate_branch(final_branch_name, config.branch)

    if not is_valid:
        typer.secho(f"\n✘ {message}", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    typer.secho("✔ Branch name is valid!", fg=typer.colors.GREEN)

    # Enforce one-branch-per-issue-per-environment rule when enabled
    if config.branch.enforce_single_branch_per_issue_env:
        try:
            existing_result = subprocess.run(
                ["git", "for-each-ref", "--format=%(refname:short)", "refs/heads/"],
                capture_output=True,
                text=True,
                check=True,
            )
            existing_branches = existing_result.stdout.splitlines()
        except subprocess.CalledProcessError:
            existing_branches = []

        is_unique, uniqueness_message = validate_single_branch_per_issue_env(
            final_branch_name, existing_branches
        )

        if not is_unique:
            typer.secho(f"\n✘ {uniqueness_message}", fg=typer.colors.RED)
            raise typer.Exit(code=1)

    # Check if branch already exists
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--verify", f"refs/heads/{final_branch_name}"], capture_output=True
        )
        if result.returncode == 0:
            typer.secho(f"\n✘ Branch '{final_branch_name}' already exists!", fg=typer.colors.RED)

            if typer.confirm("\n  Switch to existing branch?", default=False):
                subprocess.run(["git", "checkout", final_branch_name], check=True)
                typer.secho(f"\n✔ Switched to '{final_branch_name}'", fg=typer.colors.GREEN)
            raise typer.Exit(code=0)
    except subprocess.CalledProcessError:
        pass  # Branch doesn't exist, continue

    # Confirm creation
    typer.echo(f"\n📌 Ready to create branch: {final_branch_name}")
    if not typer.confirm("\n  Create and checkout?", default=True):
        typer.echo("Cancelled.")
        raise typer.Exit(code=0)

    # Create and checkout branch
    try:
        subprocess.run(["git", "checkout", "-b", final_branch_name], check=True)

        typer.echo()
        typer.secho("=" * 50, fg=typer.colors.GREEN)
        typer.secho(f"✔ Branch '{final_branch_name}' created!", fg=typer.colors.GREEN, bold=True)
        typer.secho("=" * 50, fg=typer.colors.GREEN)

        # Show next steps
        typer.echo("\n📚 Next steps:")
        typer.echo("  1. Make your changes")
        typer.echo("  2. Stage files:  git add .")
        typer.echo("  3. Commit:       git commit -m '[TAG] Your message'")
        typer.echo(f"  4. Push:         git push -u origin {final_branch_name}")
        typer.echo()

    except subprocess.CalledProcessError as e:
        typer.secho(f"\n✘ Failed to create branch: {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)


@app.command()
def commit(message: str, config_file: Optional[str] = typer.Option(None, "--config", "-c", help="Path to config file")):
    """Validate and commit changes with a properly formatted message."""
    import subprocess

    config = load_config(config_file)

    # Validate commit
    is_valid, result_message = validate_commit(message, config.commit)

    if not is_valid:
        typer.secho(f"\n✘ {result_message}", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    # Check if in git repo
    try:
        subprocess.run(["git", "rev-parse", "--git-dir"], check=True, capture_output=True)
    except subprocess.CalledProcessError:
        typer.secho("✘ Not a git repository", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    if config.commit.restrict_branch_to_owner:
        # Check branch ownership to prevent committing on another developer's branch
        try:
            branch_result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                check=True,
                capture_output=True,
                text=True,
            )
            current_branch = branch_result.stdout.strip()
        except subprocess.CalledProcessError:
            typer.secho("✘ Unable to determine current branch", fg=typer.colors.RED)
            raise typer.Exit(code=1)
    
        is_owner, ownership_message = validate_branch_ownership(current_branch)
        if not is_owner:
            typer.secho(f"✘ {ownership_message}", fg=typer.colors.RED)
            raise typer.Exit(code=1)

    if config.commit.append_issue_number:
        # Append issue number if configured and not already present
        issue_number = get_current_issue_number()
        if issue_number and f"#{issue_number}" not in message:
            message = f"#{issue_number} {message}"

    try:
        subprocess.run(["git", "commit", "-m", message], check=True)
        typer.secho("\n✔ Committed changes!", fg=typer.colors.GREEN)
    except subprocess.CalledProcessError as e:
        typer.secho(f"\n✘ Failed to commit changes: {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1) from e


@app.command()
def create_pr(
    base: str = typer.Option("develop", "--base", "-b", help="Base branch for the pull request"),
):
    """Create a GitHub pull request for the current branch against the base branch."""
    import subprocess

    _ensure_gh_installed()

    # Ensure we are in a git repo
    try:
        subprocess.run(["git", "rev-parse", "--git-dir"], check=True, capture_output=True)
    except subprocess.CalledProcessError:
        typer.secho("✘ Not a git repository", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    # Determine current branch
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
        current_branch = result.stdout.strip()
    except subprocess.CalledProcessError:
        typer.secho("✘ Unable to determine current branch", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    if current_branch == base:
        typer.secho("✘ Current branch is the same as the base branch; nothing to create a PR for.", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    # Derive PR title from branch name
    # Example: feature/add-create-pr-command -> [FTR] Add create pr command
    prefix = None
    name_part = current_branch
    if "/" in current_branch:
        prefix, name_part = current_branch.split("/", 1)

    # Map common prefixes to tags, falling back to FTR
    prefix_to_tag = {
        "feature": "FTR",
        "bugfix": "FIX",
        "hotfix": "FIX",
        "docs": "DOCS",
        "release": "REF",
    }

    tag = prefix_to_tag.get(prefix or "", "FTR")

    # Strip a leading numeric issue and hyphen if present (e.g. 123-add-thing)
    name_core = name_part
    issue_match = re.match(r"^(\d+)-(.*)$", name_core)
    if issue_match:
        name_core = issue_match.group(2)

    words = name_core.replace("_", "-").split("-")
    words = [w for w in words if w]
    humanized = " ".join(words).lower()
    if humanized:
        humanized = humanized[0].upper() + humanized[1:]

    pr_title = f"[{tag}] {humanized}" if humanized else f"[{tag}] {current_branch}"

    cmd = [
        "gh",
        "pr",
        "create",
        "--base",
        base,
        "--head",
        current_branch,
        "--title",
        pr_title,
        "--fill",
    ]

    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        typer.secho(f"✘ Failed to create pull request: {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    typer.secho(f"✔ Created pull request: {pr_title}", fg=typer.colors.GREEN)


def get_current_issue_number():
    """Get issue number from current branch"""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
        branch = result.stdout.strip()
        
        # Extract issue number from branch name (e.g., feature/ABC-123_description -> 123)
        import re
        match = re.search(r'(\d+)', branch)
        if match:
            return match.group(0)
    except subprocess.CalledProcessError:
        pass
    return None



@app.command()
def list_owned_branches():
    """Show all local Git branches owned by the current user."""

    try:
        branches = list_user_owned_branches()
    except RuntimeError as e:
        typer.secho(f"✘ {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    if not branches:
        typer.secho("No branches owned by you were found.", fg=typer.colors.YELLOW)
        raise typer.Exit(code=0)

    typer.secho("Branches owned by you:\n", fg=typer.colors.GREEN, bold=True)
    for b in branches:
        typer.echo(f"- {b}")

    raise typer.Exit(code=0)


@app.command()
def delete_branch(
    branch: Optional[str] = typer.Argument(None, help="Name of the branch to delete (omit for interactive mode)"),
    remote: str = typer.Option("origin", "--remote", "-r", help="Remote name"),
    force: bool = typer.Option(False, "--force", "-f", help="Force delete even if not merged"),
):
    """Delete a branch locally and on the remote, enforcing ownership rules."""

    import subprocess

    # Ensure we are in a git repo
    try:
        subprocess.run(["git", "rev-parse", "--git-dir"], check=True, capture_output=True)
    except subprocess.CalledProcessError:
        typer.secho("✘ Not a git repository", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    # Load owned branches first (used for interactive and validation)
    try:
        owned_branches = list_user_owned_branches()
    except RuntimeError as e:
        typer.secho(f"✘ {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    if not owned_branches:
        typer.secho("No owned branches available to delete.", fg=typer.colors.YELLOW)
        raise typer.Exit(code=0)

    # Interactive selection if branch not provided
    if branch is None:
        typer.secho("\n🗑 Delete Branch", fg=typer.colors.CYAN, bold=True)
        typer.echo("=" * 50)
        typer.echo("\n📋 Select a branch to delete:")

        for idx, b in enumerate(owned_branches, 1):
            typer.echo(f"  {idx}. {b}")

        choice = typer.prompt("\nEnter number", type=int)

        if choice < 1 or choice > len(owned_branches):
            typer.secho("✘ Invalid choice", fg=typer.colors.RED)
            raise typer.Exit(code=1)

        branch = owned_branches[choice - 1]

    # Basic safety: don't delete main shared branches through this command
    if branch in ("main", "master", "develop") or branch.startswith("release/"):
        typer.secho(f"✘ Refusing to delete shared branch '{branch}' via CLI.", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    # Prevent deleting the currently checked-out branch
    try:
        current_branch_result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
        current_branch = current_branch_result.stdout.strip()
    except subprocess.CalledProcessError:
        typer.secho("✘ Unable to determine current branch", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    if current_branch == branch:
        typer.secho("✘ Cannot delete the branch you are currently on.", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    # Enforce ownership rules before allowing delete using the same logic
    if branch not in owned_branches:
        typer.secho(
            f"✘ You are not allowed to delete branch '{branch}' because you do not own it.",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)

    # Confirm deletion
    typer.echo(f"You are about to delete branch '{branch}' locally and from remote '{remote}'.")
    if not typer.confirm("  Continue?", default=False):
        typer.echo("Cancelled.")
        raise typer.Exit(code=0)

    # Delete local branch
    delete_flag = "-D" if force else "-d"
    try:
        subprocess.run(["git", "branch", delete_flag, branch], check=True)
        typer.secho(f"✔ Deleted local branch '{branch}'", fg=typer.colors.GREEN)
    except subprocess.CalledProcessError as e:
        typer.secho(f"✘ Failed to delete local branch '{branch}': {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    # Delete remote branch
    try:
        subprocess.run(["git", "push", remote, "--delete", branch], check=True)
        typer.secho(f"✔ Deleted remote branch '{branch}' from '{remote}'", fg=typer.colors.GREEN)
    except subprocess.CalledProcessError as e:
        typer.secho(f"✘ Failed to delete remote branch '{branch}' from '{remote}': {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    raise typer.Exit(code=0)


@app.command()
def update_issue_status(
    issue: int = typer.Argument(..., help="Issue number (e.g. 123)"),
    status: str = typer.Option(..., "--status", "-s", help="New project status value"),
    project: str = typer.Option(
        ..., "--project", "-p", help="GitHub project number or key (uses 'gh project item-list')"
    ),
    item_id: Optional[str] = typer.Option(
        None,
        "--item-id",
        help="Direct GitHub Project item id (skips searching by issue number)",
    ),
):
    """Update the Status field of a GitHub Project item for a given issue."""

    _ensure_gh_installed()

    # Load config to validate allowed statuses
    config = load_config(None)
    configured_statuses = getattr(config.github, "valid_statuses", None)
    if configured_statuses:
        valid_statuses = list(configured_statuses)
    else:
        # Fallback to built-in defaults if config key is missing
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

    if status not in valid_statuses:
        allowed = ", ".join(valid_statuses)
        typer.secho(
            f"✘ Invalid status '{status}'. Allowed values: {allowed}",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)

    # Resolve project owner and number using existing logic
    owner, project_number = _resolve_project_number(project)

    # Determine which project item to update: direct item id or lookup by issue
    if item_id is not None:
        item_title = _get_project_item_title_by_id(owner, project_number, item_id)
    else:
        item_id, item_title = _find_project_item_for_issue(owner, project_number, issue)

    # Resolve project node id and Status field/option ids
    project_id = _get_project_id(owner, project_number)
    status_field_id = _get_status_field_id(owner, project_number)
    status_option_id = _get_status_option_id(owner, project_number, status)

    cmd = [
        "gh",
        "project",
        "item-edit",
        "--id",
        item_id,
        "--field-id",
        status_field_id,
        "--project-id",
        project_id,
        "--single-select-option-id",
        status_option_id,
    ]

    try:
        subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        typer.secho(
            f"✘ Failed to update project item status: {e}",
            fg=typer.colors.RED,
        )
        if e.stderr:
            typer.echo(e.stderr)
        raise typer.Exit(code=1)

    typer.secho(
        f"✔ Updated status of project item for issue #{issue} to '{status}' (title: {item_title})",
        fg=typer.colors.GREEN,
    )


@app.command()
def list_issues(
    state: str = typer.Option(
        "open",
        "--state",
        "-s",
        help="Issue state: open, closed, or all",
    ),
    limit: int = typer.Option(
        30,
        "--limit",
        "-L",
        help="Maximum number of issues to list",
    ),
    assignee: Optional[str] = typer.Option(
        None,
        "--assignee",
        "-a",
        help="Filter by assignee (GitHub username)",
    ),
    project: Optional[str] = typer.Option(
        None,
        "--project",
        "-p",
        help="GitHub project number or key (uses 'gh project item-list')",
    ),
):
    """List GitHub issues using the gh CLI."""
    _ensure_gh_installed()

    # When a project is provided, list project items instead of issues
    if project is not None:
        project_str = str(project)

        # Special value 'all' -> list items for all configured projects in [github.projects]
        if project_str.lower() == "all":
            config = load_config(None)
            owner = getattr(config.github, "owner", None)
            projects_map = getattr(config.github, "projects", {}) or {}

            if not owner:
                typer.secho(
                    "✘ GitHub owner must be configured in the config file under the [github] section to use --project all.",
                    fg=typer.colors.RED,
                )
                raise typer.Exit(code=1)

            if not projects_map:
                typer.secho(
                    "✘ No projects configured under [github.projects] to use with --project all.",
                    fg=typer.colors.RED,
                )
                raise typer.Exit(code=1)

            # Iterate all configured project keys and list items for each
            for key in sorted(projects_map.keys()):
                owner_for_key, project_number_for_key = _resolve_project_number(key)

                cmd = [
                    "gh",
                    "project",
                    "item-list",
                    project_number_for_key,
                    "--owner",
                    owner_for_key,
                    "--limit",
                    str(limit),
                    "--format",
                    "json",
                ]

                try:
                    result = subprocess.run(
                        cmd,
                        check=True,
                        capture_output=True,
                        text=True,
                    )
                except subprocess.CalledProcessError as e:
                    typer.secho(
                        f"✘ Failed to run gh command for project '{key}': {e}",
                        fg=typer.colors.RED,
                    )
                    if e.stderr:
                        typer.echo(e.stderr)
                    raise typer.Exit(code=1)

                _print_project_items(result.stdout, assignee)

            # All projects processed; nothing else to do
            return

        # Single project path
        owner, project_number = _resolve_project_number(project)

        cmd = [
            "gh",
            "project",
            "item-list",
            project_number,
            "--owner",
            owner,
            "--limit",
            str(limit),
            "--format",
            "json",
        ]
    else:
        cmd = ["gh", "issue", "list", "--state", state, "--limit", str(limit)]

        if assignee:
            cmd.extend(["--assignee", assignee])

    try:
        result = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        typer.secho(
            f"✘ Failed to run gh command: {e}",
            fg=typer.colors.RED,
        )
        if e.stderr:
            typer.echo(e.stderr)
        raise typer.Exit(code=1)

    # For project mode, parse JSON and show only title, status, and priority
    if project is not None:
        _print_project_items(result.stdout, assignee)
    else:
        # Default behavior for issues: print raw gh output
        typer.echo(result.stdout)


def _ensure_gh_installed() -> None:
    # Ensure gh is installed
    if shutil.which("gh") is None:
        typer.secho(
            "✘ GitHub CLI 'gh' is not installed or not in PATH. "
            "Install it from https://cli.github.com/.",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)


def _resolve_project_number(project: str):
    config = load_config(None)
    owner = getattr(config.github, "owner", None)

    if not owner:
        typer.secho(
            "✘ GitHub owner must be configured in the config file under the [github] section to use --project.",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)

    # Resolve project to a numeric ID: either directly numeric or via config.github.projects
    project_str = str(project)
    project_number = None

    if project_str.isdigit():
        project_number = project_str
    else:
        projects_map = getattr(config.github, "projects", {}) or {}
        raw_value = projects_map.get(project_str)

        if raw_value is None:
            available = ", ".join(sorted(projects_map.keys())) or "<none>"
            typer.secho(
                f"✘ Unknown project key '{project_str}'. Available keys: {available}",
                fg=typer.colors.RED,
            )
            raise typer.Exit(code=1)

        # Support values like "Way Cloud SaaS (#4)" or "Project #4"
        match = re.search(r"(\d+)", str(raw_value))
        if match:
            project_number = match.group(1)
        else:
            # Fallback: if the raw value itself is numeric, use it directly
            raw_str = str(raw_value).strip()
            if raw_str.isdigit():
                project_number = raw_str

    if project_number is None:
        typer.secho(
            f"✘ Unable to determine numeric project ID from '{project}'. Configure it as a number or include '#<id>' in the value.",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)

    return owner, project_number


def _print_project_items(stdout: str, assignee: Optional[str]):
    try:
        data = json.loads(stdout or "{}")
    except json.JSONDecodeError:
        typer.echo(stdout)
        raise typer.Exit(code=1)

    # gh project item-list may return an object with an "items" array or a raw array
    if isinstance(data, dict) and "items" in data:
        items = data.get("items", [])
    elif isinstance(data, list):
        items = data
    else:
        items = []

    # Optional filter by assignee when available
    if assignee:
        assignee_lower = assignee.lower()
        filtered_items = []
        for item in items:
            content = item.get("content", {}) or {}

            # Collect assignee usernames from both top-level and content
            raw_assignees = []
            top_level = item.get("assignees") or []
            content_level = content.get("assignees") or []

            if isinstance(top_level, list):
                raw_assignees.extend(top_level)
            if isinstance(content_level, list):
                raw_assignees.extend(content_level)

            usernames = []
            for a in raw_assignees:
                if isinstance(a, str):
                    usernames.append(a)
                elif isinstance(a, dict):
                    login = a.get("login") or a.get("name")
                    if login:
                        usernames.append(login)

            if any(u.lower() == assignee_lower for u in usernames):
                filtered_items.append(item)

        items = filtered_items

    if not items:
        typer.echo("No project items found.")
        return

    # Load emoji mapping from config when available
    config = load_config(None)
    configured_emojis = getattr(config.github, "status_emojis", None)

    # Helper to normalize status keys (for both config and runtime values)
    def _norm_status_key(value: str) -> str:
        return (value or "").strip().lower().replace(" ", "_")

    if configured_emojis:
        raw_emojis = dict(configured_emojis)
    else:
        raw_emojis = {
            "Backlog": "📋",
            "Blocked": "⛔",
            "To Do": "📝",
            "In Progress": "🚧",
            "Waiting Integration": "🔄",
            "QA Testing": "🧪",
            "QA In Progress": "🔬",
            "QA Approved": "✅",
            "Pending To Deploy": "⏳",
            "Done": "🏁",
        }

    # Build normalized emoji mapping
    status_emojis = {
        _norm_status_key(name): emoji for name, emoji in raw_emojis.items()
    }

    # Optional: warn if some configured statuses do not have an emoji mapping
    configured_statuses = getattr(config.github, "valid_statuses", None)
    if configured_statuses:
        missing_emoji_statuses = [
            s for s in configured_statuses if _norm_status_key(s) not in status_emojis
        ]
        if missing_emoji_statuses:
            missing_str = ", ".join(missing_emoji_statuses)
            typer.secho(
                f"⚠ Some statuses do not have emojis configured: {missing_str}",
                fg=typer.colors.YELLOW,
            )

    for item in items:
        content = item.get("content", {}) or {}
        title = item.get("title") or content.get("title", "")
        status = item.get("status", "")
        priority = item.get("priority", "")
        number = content.get("number")

        emoji = status_emojis.get(_norm_status_key(status), "•")

        if number is not None:
            # Include underlying issue number when available
            typer.echo(f"{emoji} #{number} [{status or '-'}] ({priority or '-'}) {title}")
        else:
            # Fallback when no number is present
            typer.echo(f"{emoji} [{status or '-'}] ({priority or '-'}) {title}")


def _get_project_id(owner: str, project_number: str) -> str:
    cmd = [
        "gh",
        "project",
        "view",
        project_number,
        "--owner",
        owner,
        "--format",
        "json",
    ]

    try:
        result = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        typer.secho(
            f"✘ Failed to get project info: {e}",
            fg=typer.colors.RED,
        )
        if e.stderr:
            typer.echo(e.stderr)
        raise typer.Exit(code=1)

    try:
        data = json.loads(result.stdout or "{}")
    except json.JSONDecodeError:
        typer.echo(result.stdout)
        raise typer.Exit(code=1)

    project_id = data.get("id")
    if not project_id:
        typer.secho("✘ Unable to determine project id from gh project view output.", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    return project_id


def _get_status_field_id(owner: str, project_number: str) -> str:
    cmd = [
        "gh",
        "project",
        "field-list",
        project_number,
        "--owner",
        owner,
        "--format",
        "json",
    ]

    try:
        result = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        typer.secho(
            f"✘ Failed to list project fields: {e}",
            fg=typer.colors.RED,
        )
        if e.stderr:
            typer.echo(e.stderr)
        raise typer.Exit(code=1)

    try:
        data = json.loads(result.stdout or "[]")
    except json.JSONDecodeError:
        typer.echo(result.stdout)
        raise typer.Exit(code=1)

    if isinstance(data, dict) and "fields" in data:
        fields = data.get("fields", [])
    else:
        fields = data

    for field in fields:
        if field.get("name") == "Status":
            field_id = field.get("id")
            if field_id:
                return field_id

    typer.secho("✘ Could not find a 'Status' field in the project.", fg=typer.colors.RED)
    raise typer.Exit(code=1)


def _get_status_option_id(owner: str, project_number: str, status: str) -> str:
    cmd = [
        "gh",
        "project",
        "field-list",
        project_number,
        "--owner",
        owner,
        "--format",
        "json",
    ]

    try:
        result = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        typer.secho(
            f"✘ Failed to list project fields: {e}",
            fg=typer.colors.RED,
        )
        if e.stderr:
            typer.echo(e.stderr)
        raise typer.Exit(code=1)

    try:
        data = json.loads(result.stdout or "[]")
    except json.JSONDecodeError:
        typer.echo(result.stdout)
        raise typer.Exit(code=1)

    if isinstance(data, dict) and "fields" in data:
        fields = data.get("fields", [])
    else:
        fields = data

    for field in fields:
        if field.get("name") != "Status":
            continue

        options = field.get("options") or []
        for opt in options:
            if opt.get("name") == status:
                option_id = opt.get("id")
                if option_id:
                    return option_id

    typer.secho(
        f"✘ Could not find a Status option named '{status}' in the project.",
        fg=typer.colors.RED,
    )
    raise typer.Exit(code=1)


def _find_project_item_for_issue(owner: str, project_number: str, issue: int):
    cmd = [
        "gh",
        "project",
        "item-list",
        project_number,
        "--owner",
        owner,
        "--format",
        "json",
    ]

    try:
        result = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        typer.secho(
            f"✘ Failed to list project items: {e}",
            fg=typer.colors.RED,
        )
        if e.stderr:
            typer.echo(e.stderr)
        raise typer.Exit(code=1)

    items = _parse_project_items(result.stdout)
    item = _select_single_item_for_issue(items, issue)

    item_id = item.get("id")
    title = item.get("title") or item.get("content", {}).get("title", "")

    if not item_id:
        typer.secho("✘ Matching project item does not have an 'id' field.", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    return item_id, title


def _parse_project_items(stdout: str):
    try:
        data = json.loads(stdout or "[]")
    except json.JSONDecodeError:
        typer.echo(stdout)
        raise typer.Exit(code=1)

    if isinstance(data, dict) and "items" in data:
        items = data.get("items", [])
    else:
        items = data

    if not items:
        typer.secho("✘ No project items found in the project.", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    return items


def _select_single_item_for_issue(items, issue: int):
    issue_str = str(issue)
    needle_hash = f"#{issue_str}"

    matches = []
    for item in items:
        raw_type = item.get("type") or ""
        content = item.get("content", {}) or {}
        content_url = content.get("url", "") or ""

        # Determine whether this project item represents an *issue* (and not a PR)
        # - gh project item-list typically uses upper-case types like "ISSUE" / "PULL_REQUEST"
        # - content.url generally contains either "/issues/" or "/pull/"
        norm_type = str(raw_type).strip().lower()
        is_issue = "issues" in content_url or norm_type == "issue"

        title = item.get("title") or content.get("title", "")
        if not title:
            continue

        # Prefer a '#<issue>' match, but fall back to raw number in title if needed
        if (needle_hash in title or (issue_str in title and needle_hash not in title)) and is_issue:
            matches.append(item)
            continue

        # As a more reliable fallback, also match by underlying content.number
        number = content.get("number")
        if number is not None and str(number) == issue_str and is_issue:
            matches.append(item)

    if not matches:
        typer.secho(
            f" Could not find a project item with issue number #{issue} in the title.",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)

    if len(matches) > 1:
        typer.secho(
            f"✘ Multiple project items match issue number #{issue}. Please disambiguate.",
            fg=typer.colors.RED,
        )
        for item in matches:
            title = item.get("title") or item.get("content", {}).get("title", "")
            typer.echo(f"- {title}")
        raise typer.Exit(code=1)

    return matches[0]


def _get_project_item_title_by_id(owner: str, project_number: str, item_id: str) -> str:
    cmd = [
        "gh",
        "project",
        "item-list",
        project_number,
        "--owner",
        owner,
        "--format",
        "json",
    ]

    try:
        result = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        typer.secho(
            f"✘ Failed to list project items: {e}",
            fg=typer.colors.RED,
        )
        if e.stderr:
            typer.echo(e.stderr)
        raise typer.Exit(code=1)

    items = _parse_project_items(result.stdout)
    for item in items:
        if str(item.get("id")) == str(item_id):
            return item.get("title") or item.get("content", {}).get("title", "")

    typer.secho(
        f"✘ Could not find a project item with id '{item_id}' in the project.",
        fg=typer.colors.RED,
    )
    raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
