import re
import string
import subprocess

import typer
from yaspin import yaspin

from devrules.config import Config
from devrules.dtos.github import ProjectItem
from devrules.messages import git as msg
from devrules.utils import gum
from devrules.utils.typer import add_typer_block_message


def ensure_git_repo() -> None:
    """Ensure we are in a git repository."""
    try:
        subprocess.run(["git", "rev-parse", "--git-dir"], check=True, capture_output=True)
    except subprocess.CalledProcessError:
        typer.secho(msg.NOT_A_GIT_REPOSITORY, fg=typer.colors.RED)
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
        typer.secho(msg.UNABLE_TO_DETERMINE_CURRENT_BRANCH, fg=typer.colors.RED)
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

        add_typer_block_message(
            header=f"✔ Branch '{branch_name}' created!",
            subheader="📚 Next steps:",
            messages=[
                "1. Make your changes",
                "2. Stage files:  git add .",
                "3. Commit:       git commit -m 'Your message'",
                "4. Push:         git push -u origin {}".format(branch_name),
            ],
        )

    except subprocess.CalledProcessError as e:
        typer.secho(msg.FAILED_TO_CREATE_BRANCH.format(e), fg=typer.colors.RED)
        raise typer.Exit(code=1)


def handle_existing_branch(branch_name: str) -> None:
    """Check if branch exists and offer to switch to it."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--verify", f"refs/heads/{branch_name}"], capture_output=True
        )
        if result.returncode == 0:
            typer.secho(msg.BRANCH_NAME_ALREADY_EXISTS.format(branch_name), fg=typer.colors.RED)

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
    """Get branch name through interactive prompts.

    Uses gum for enhanced UI if available, falls back to typer prompts.
    """
    # Use gum if available for enhanced UI
    if gum.is_available():
        return _get_branch_name_with_gum(config)
    else:
        return _get_branch_name_with_typer(config)


def _get_branch_name_with_gum(config: Config) -> str:
    """Get branch name using gum for enhanced UI."""
    # Header
    print(gum.style("🌿 Create New Branch", foreground=81, bold=True))
    print(gum.style("=" * 50, foreground=81))

    # Step 1: Select branch type
    branch_type = gum.choose(
        config.branch.prefixes,
        header="📋 Select branch type:",
    )

    if not branch_type:
        typer.secho("✘ No branch type selected", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    # Step 2: Issue/ticket number (optional)
    issue_number = gum.input_text_with_history(
        prompt_type="issue_number",
        placeholder="Enter number or leave empty to skip",
        header="🔢 Issue/ticket number (optional):",
    )

    # Step 3: Branch description
    description = gum.input_text_with_history(
        prompt_type="branch_description",
        placeholder="Enter a short description of branch intent",
        header="📝 Branch description:",
    )

    if not description:
        gum.error(msg.DESCRIPTION_CAN_NOT_BE_EMPTY)
        raise typer.Exit(code=1)

    # Clean and format description
    description = sanitize_description(description)

    if not description:
        gum.error("Description cannot be empty after sanitization")
        raise typer.Exit(code=1)

    # Build branch name
    if issue_number:
        return f"{branch_type}/{issue_number}-{description}"
    else:
        return f"{branch_type}/{description}"


def _get_branch_name_with_typer(config: Config) -> str:
    """Get branch name using typer prompts (fallback)."""
    add_typer_block_message(
        header="🌿 Create New Branch",
        subheader="📋 Select branch type:",
        messages=[f"{idx}. {prefix}" for idx, prefix in enumerate(config.branch.prefixes, 1)],
    )

    type_choice = typer.prompt("Enter number", type=int, default=1)

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
        typer.secho(msg.DESCRIPTION_CAN_NOT_BE_EMPTY, fg=typer.colors.RED)
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
    """Resolve branch name from project item title.

    Sanitizes the title by removing punctuation and joining words with hyphens.
    """
    translator = str.maketrans("", "", string.punctuation)
    sanitized = project_item.title.lower().translate(translator).split()
    return f"{scope}/{issue}-{'-'.join(sanitized)}"


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


def get_merged_branches(base_branch: str = "develop") -> list[str]:
    """Get list of branches merged into the base branch."""
    try:
        result = subprocess.run(
            ["git", "branch", "--merged", base_branch],
            capture_output=True,
            text=True,
            check=True,
        )
        # Filter out '*' (current branch marker) and whitespace
        branches = [b.strip().lstrip("* ") for b in result.stdout.splitlines() if b.strip()]
        return branches
    except subprocess.CalledProcessError:
        return []


def delete_branch_local_and_remote(
    branch: str, remote: str = "origin", force: bool = False, ignore_remote_error: bool = False
) -> None:
    """Delete a branch locally and on the remote."""
    # Delete local branch
    delete_flag = "-D" if force else "-d"
    try:
        with yaspin(text=f"Deleting local branch '{branch}'"):
            subprocess.run(["git", "branch", delete_flag, branch], check=True, capture_output=True)
        typer.secho(f"✔ Deleted local branch '{branch}'", fg=typer.colors.GREEN)
    except subprocess.CalledProcessError as e:
        typer.secho(
            f"✘ Failed to delete local branch '{branch}': {e.stderr.decode().strip()}",
            fg=typer.colors.RED,
        )
        if not ignore_remote_error:
            raise typer.Exit(code=1)

    # Delete remote branch
    if not offline_remote_branch_exists(branch=branch):
        typer.secho("Branch does not exists remotely, skipping...", fg=typer.colors.YELLOW)
    else:
        try:
            with yaspin(text=f"Deleting remote branch '{branch}' from '{remote}'"):
                subprocess.run(
                    ["git", "push", remote, "--delete", branch], check=True, capture_output=True
                )
            typer.secho(
                f"✔ Deleted remote branch '{branch}' from '{remote}'", fg=typer.colors.GREEN
            )
        except subprocess.CalledProcessError as e:
            if ignore_remote_error:
                typer.secho(
                    f"⚠ Could not delete remote branch '{branch}' (maybe it doesn't exist?)",
                    fg=typer.colors.YELLOW,
                )
            else:
                typer.secho(
                    f"✘ Failed to delete remote branch '{branch}' from '{remote}': {e.stderr.decode().strip()}",
                    fg=typer.colors.RED,
                )
                raise typer.Exit(code=1)


def checkout_branch_interactive(config: Config) -> None:
    """Interactively select and checkout a branch."""
    ensure_git_repo()

    current_branch = get_current_branch()
    branches = get_existing_branches()

    # Filter out current branch from candidates
    candidates = [b for b in branches if b != current_branch]

    if not candidates:
        typer.secho("✘ No other branches found to switch to.", fg=typer.colors.YELLOW)
        raise typer.Exit(code=0)

    selected_branch = None

    # Use gum if available
    if gum.is_available():
        print(gum.style("🔀 Switch Branch", foreground=81, bold=True))
        print(gum.style(f"Current: {current_branch}", foreground=240))

        # Use filter so user can search
        selected_branch = gum.filter_list(
            candidates, placeholder="Select branch to checkout...", header="Branches"
        )
    else:
        # Fallback to typer prompt
        add_typer_block_message(
            header="🔀 Switch Branch",
            subheader=f"Current: {current_branch}",
            messages=[f"{idx}. {b}" for idx, b in enumerate(candidates, 1)],
        )

        choice = typer.prompt("Enter number", type=int)

        if 1 <= choice <= len(candidates):
            selected_branch = candidates[choice - 1]

    if not selected_branch:
        typer.echo("Cancelled.")
        raise typer.Exit(code=0)

    try:
        subprocess.run(["git", "checkout", selected_branch], check=True)
        typer.secho(f"\n✔ Switched to branch '{selected_branch}'", fg=typer.colors.GREEN)
    except subprocess.CalledProcessError as e:
        typer.secho(f"\n✘ Failed to checkout branch: {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)


def remote_branch_exists(branch: str, remote: str = "origin") -> bool:
    """Check if a branch exists on the remote."""
    try:
        subprocess.run(
            ["git", "ls-remote", "--exit-code", "--heads", remote, branch],
            check=True,
            capture_output=True,
        )
        return True
    except subprocess.CalledProcessError:
        return False


def offline_remote_branch_exists(branch: str, remote: str = "origin") -> bool:
    """Check if a branch exists on the remote without consulting network"""
    try:
        result = subprocess.run(
            ["git", "branch", "-a"],
            check=True,
            capture_output=True,
        )
        output_lines = result.stdout.splitlines()
        str_output_lines = [output.decode().strip() for output in output_lines]
        if f"remotes/{remote}/{branch}" in str_output_lines:
            return True
        else:
            return False
    except subprocess.CalledProcessError:
        return False
