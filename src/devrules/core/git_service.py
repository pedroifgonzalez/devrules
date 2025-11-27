import subprocess

import typer
import re
from devrules.config import Config
from devrules.dtos.github import ProjectItem


def ensure_git_repo() -> None:
    """Ensure we are in a git repository."""
    try:
        subprocess.run(["git", "rev-parse", "--git-dir"], check=True, capture_output=True)
    except subprocess.CalledProcessError:
        typer.secho("✘ Not a git repository", fg=typer.colors.RED)
        raise typer.Exit(code=1)


def get_current_branch() -> str:
    """Get the name of the current git branch."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        typer.secho("✘ Unable to determine current branch", fg=typer.colors.RED)
        raise typer.Exit(code=1)


def get_existing_branches() -> list[str]:
    """Get list of existing local branches."""
    try:
        result = subprocess.run(
            ["git", "for-each-ref", "--format=%(refname:short)", "refs/heads/"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.splitlines()
    except subprocess.CalledProcessError:
        return []


def create_and_checkout_branch(branch_name: str) -> None:
    """Create and checkout the new branch, showing success message."""
    try:
        subprocess.run(["git", "checkout", "-b", branch_name], check=True)

        typer.echo()
        typer.secho("=" * 50, fg=typer.colors.GREEN)
        typer.secho(f"✔ Branch '{branch_name}' created!", fg=typer.colors.GREEN, bold=True)
        typer.secho("=" * 50, fg=typer.colors.GREEN)

        # Show next steps
        typer.echo("\n📚 Next steps:")
        typer.echo("  1. Make your changes")
        typer.echo("  2. Stage files:  git add .")
        typer.echo("  3. Commit:       git commit -m '[TAG] Your message'")
        typer.echo(f"  4. Push:         git push -u origin {branch_name}")
        typer.echo()

    except subprocess.CalledProcessError as e:
        typer.secho(f"\n✘ Failed to create branch: {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)


def handle_existing_branch(branch_name: str) -> None:
    """Check if branch exists and offer to switch to it."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--verify", f"refs/heads/{branch_name}"], capture_output=True
        )
        if result.returncode == 0:
            typer.secho(f"\n✘ Branch '{branch_name}' already exists!", fg=typer.colors.RED)

            if typer.confirm("\n  Switch to existing branch?", default=False):
                subprocess.run(["git", "checkout", branch_name], check=True)
                typer.secho(f"\n✔ Switched to '{branch_name}'", fg=typer.colors.GREEN)
            raise typer.Exit(code=0)
    except subprocess.CalledProcessError:
        pass  # Branch doesn't exist, continue


def sanitize_description(description: str) -> str:
    """Clean and format branch description."""
    description = description.lower().strip()
    description = re.sub(r"[^a-z0-9-]", "-", description)
    description = re.sub(r"-+", "-", description)  # Remove multiple hyphens
    description = description.strip("-")  # Remove leading/trailing hyphens
    return description


def get_branch_name_interactive(config: Config) -> str:
    """Get branch name through interactive prompts."""
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
    description = sanitize_description(description)

    if not description:
        typer.secho("✘ Description cannot be empty", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    # Build branch name
    if issue_number:
        return f"{branch_type}/{issue_number}-{description}"
    else:
        return f"{branch_type}/{description}"


def detect_scope(config: Config, project_item: ProjectItem) -> str:
    # Detect the scope based on the project item with hierarchy
    scope = config.branch.prefixes[0]
    labels_mappping = config.branch.labels_mapping
    if not project_item.labels:
        return scope

    # Build scope priority from config (higher index = higher priority)
    scope_priority = {}
    if config.branch.labels_hierarchy:
        for idx, scope_name in enumerate(config.branch.labels_hierarchy, start=1):
            scope_priority[scope_name] = idx

    # Find the highest priority scope among matching labels
    best_scope = None
    best_priority = 0

    for label in project_item.labels:
        if label in labels_mappping:
            mapped_scope = labels_mappping[label]
            priority = scope_priority.get(mapped_scope, 0)
            if priority > best_priority:
                best_priority = priority
                best_scope = mapped_scope

    if best_scope:
        scope = best_scope

    return scope


def create_staging_branch_name(current_branch: str) -> str:
    """Transform a branch name to its staging variant.

    Example: feature/23-do-something -> staging-23-do-something
    """
    # Remove the prefix (e.g., feature/, bugfix/, etc.) if present
    if "/" in current_branch:
        _, branch_suffix = current_branch.split("/", 1)
    else:
        branch_suffix = current_branch

    return f"staging-{branch_suffix}"


def resolve_issue_branch(scope: str, project_item: ProjectItem, issue: int) -> str:
    # Resolve the branch name based on the project item
    words = project_item.title.lower().split()
    branch_name = f"{scope}/{issue}-{'-'.join(words)}"
    return branch_name


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

        match = re.search(r"(\d+)", branch)
        if match:
            return match.group(0)
    except subprocess.CalledProcessError:
        pass
    return None
