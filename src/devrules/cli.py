"""Command-line interface for DevRules."""

import os
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
    owner: str,
    repo: str,
    pr_number: int,
    config_file: Optional[str] = typer.Option(None, "--config", "-c", help="Path to config file"),
):
    """Validate PR size and title format."""
    config = load_config(config_file)

    try:
        pr_info = fetch_pr_info(owner, repo, pr_number, config.github)
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

[pr]
max_loc = 400
max_files = 20
require_title_tag = true
title_pattern = "^\\\\[({tags})\\\\].+"

[github]
api_url = "https://api.github.com"
timeout = 30
"""

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

    try:
        subprocess.run(["git", "commit", "-m", message], check=True)
        typer.secho("\n✔ Committed changes!", fg=typer.colors.GREEN)
    except subprocess.CalledProcessError as e:
        typer.secho(f"\n✘ Failed to commit changes: {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1) from e


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
):
    """List GitHub issues using the gh CLI."""
    import subprocess
    import shutil

    # Ensure gh is installed
    if shutil.which("gh") is None:
        typer.secho(
            "✘ GitHub CLI 'gh' is not installed or not in PATH. "
            "Install it from https://cli.github.com/.",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)

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
            f"✘ Failed to list issues via gh: {e}",
            fg=typer.colors.RED,
        )
        if e.stderr:
            typer.echo(e.stderr)
        raise typer.Exit(code=1)

    typer.echo(result.stdout)


if __name__ == "__main__":
    app()
