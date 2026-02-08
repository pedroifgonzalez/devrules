"""CLI commands for branch management."""

from typing import Any, Callable, Dict, Optional

import typer
from typer_di import Depends
from yaspin import yaspin

from devrules.adapters.prompters.factory import get_default_prompter
from devrules.cli_commands.commons import _fetch_project_items, _get_issue_and_status_interactively
from devrules.config import Config, load_config
from devrules.core.git_service import (
    checkout_branch,
    create_and_checkout_branch,
    create_staging_branch_name,
    delete_branch_local_and_remote,
    detect_scope,
    get_current_branch,
    get_existing_branches,
    get_merged_branches,
    handle_existing_branch,
    merge_branch,
    resolve_issue_branch,
    sanitize_text,
)
from devrules.core.project_service import find_project_item_for_issue, resolve_project_number
from devrules.messages import branch as msg
from devrules.messages import git as git_msg
from devrules.utils.decorators import ensure_git_repo
from devrules.utils.dependencies import get_config
from devrules.utils.issue_mapping import get_issue_mapping_manager
from devrules.validators.branch import (
    _extract_issue_number,
    validate_branch,
    validate_cross_repo_card,
    validate_single_branch_per_issue_env,
)
from devrules.validators.ownership import list_user_owned_branches
from devrules.validators.repo_state import display_repo_state_issues, validate_repo_state

prompter = get_default_prompter()


def check_repo_state(config: Config, skip_checks: bool = False):
    if not skip_checks and at_least_one_validation_repo_state_set(config):
        with yaspin(text="Checking repository state...") as spinner:
            is_valid, messages = validate_repo_state(
                check_uncommitted=config.validation.check_uncommitted,
                check_behind=config.validation.check_behind_remote,
                warn_only=config.validation.warn_only,
            )
            spinner.ok("✔")
            spinner.stop()

        if not is_valid:
            display_repo_state_issues(messages, warn_only=False)
            raise prompter.exit(code=1)


def _get_available_branches_to_integrate_with(current_branch: str) -> list[str]:
    branches = get_existing_branches()

    # Filter out current branch from candidates (it's already the base)
    candidates = [b for b in branches if b != current_branch]

    if not candidates:
        prompter.warning("No other branches available to integrate.")
        raise prompter.exit(code=0)

    # Select branches to integrate
    branches_to_integrate = prompter.choose(
        header="Select branches to integrate:",
        options=candidates,
        limit=0,
    )

    # Validate that at least one branch was selected
    if not branches_to_integrate:
        prompter.warning("No branches selected. Operation cancelled.")
        raise prompter.exit(code=0)

    assert isinstance(branches_to_integrate, list)
    return branches_to_integrate


def _show_integration_options(current_branch: str, branches_to_integrate: list[str]) -> None:
    prompter.info(f"Base branch: {current_branch}")
    prompter.info("Branches to integrate:")
    for no, branch in enumerate(branches_to_integrate, start=1):
        prompter.indented_message(f"{no}. {branch}")


def _confirm_integration(current_branch: str, branches_to_integrate: list[str]) -> None:
    _show_integration_options(current_branch, branches_to_integrate)
    confirm = prompter.confirm("Create integration branch with these branches?")
    if not confirm:
        prompter.warning("Branch creation cancelled")
        raise prompter.exit(code=0)


def _get_integration_branch_name(
    config: Config, prefix: str, branches_to_integrate: list[str]
) -> str:
    # Build suggested branch name from issue numbers
    suggested_name = prefix
    for branch in branches_to_integrate:
        issue = _extract_issue_number(branch_name=branch)
        if issue:
            suggested_name += f"-{issue}" if branch != branches_to_integrate[0] else f"/{issue}"
    branch_name = prompter.write(
        placeholder="Type a branch name...",
        header="Enter a branch name:",
        default=suggested_name,
    )
    if not branch_name:
        prompter.error("Branch name cannot be empty")
        raise prompter.exit(code=1)

    # Validate branch name
    with yaspin(text=f"Validating branch name: {branch_name}") as spinner:
        is_valid, message = validate_branch(branch_name, config.branch)
        spinner.ok("✔")

    if not is_valid:
        prompter.error(message)
        raise prompter.exit(code=1)
    return branch_name


def _perform_integration(new_branch: str, current_branch: str, branches_to_integrate: list[str]):
    handle_existing_branch(new_branch)
    prompter.info(f"Creating integration branch '{new_branch}' from '{current_branch}'...")
    create_and_checkout_branch(new_branch)
    # Merge each selected branch into the integration branch
    for branch in branches_to_integrate:
        prompter.info(f"Fetching and merging '{branch}'...")
        # Fetch the latest changes for the branch
        checkout_branch(branch, fetch_first=True)
        # Return to integration branch
        checkout_branch(new_branch, fetch_first=False)
        # Merge the branch into integration branch
        success, message = merge_branch(branch, new_branch)
        if not success:
            prompter.error(f"Merge conflict detected while merging '{branch}'")
            prompter.info("To resolve conflicts:")
            prompter.indented_message("1. Check conflicted files: git status")
            prompter.indented_message("2. Resolve conflicts in your editor")
            prompter.indented_message("3. Stage resolved files: git add <file>")
            prompter.indented_message("4. Complete merge: git commit")
            prompter.indented_message("5. Continue merging remaining branches manually")
            prompter.warning(f"Integration branch '{new_branch}' is partially complete.")
            raise prompter.exit(code=1)
        prompter.success(f"Merged '{branch}' successfully")
    prompter.success(f"Integration branch '{new_branch}' created successfully!")
    prompter.info("Next steps:")
    prompter.indented_message("1. Review the integrated changes")
    prompter.indented_message(f"2. Push: git push -u origin {new_branch}")


def at_least_one_validation_repo_state_set(config: Config):
    return any((config.validation.check_uncommitted, config.validation.check_behind_remote))


def checkout_branch_interactive(branch: str | None = None) -> None:
    """Interactively select and checkout a branch."""
    if branch:
        result, message = checkout_branch(branch)
        if result is True:
            prompter.success(message)
        else:
            prompter.error(f"Failed to checkout branch: {message}")
            raise prompter.exit(code=1)
        return

    current_branch = get_current_branch()
    branches = get_existing_branches()

    # Filter out current branch from candidates
    candidates = [b for b in branches if b != current_branch]

    if not candidates:
        prompter.warning("No other branches found to switch to.")
        raise prompter.exit(code=0)

    selected_branch = None
    # Use filter so user can search
    selected_branch = prompter.filter_list(
        candidates, placeholder="Select branch to checkout...", header="Branches"
    )
    if not selected_branch:
        prompter.error("Cancelled.")
        raise prompter.exit(code=0)

    result, message = checkout_branch(selected_branch)
    if result is True:
        prompter.success(message)
    else:
        prompter.error(f"Failed to checkout branch: {message}")
        raise prompter.exit(code=1)


def _get_branch_name_interactive(config: Config):
    """Conform a branch name interactively"""

    branch_type = prompter.choose(
        options=config.branch.prefixes,
        header="Select branch type:",
    )

    if not branch_type:
        prompter.error("No branch type selected")
        raise prompter.exit(1)

    # Step 2: Issue/ticket number (optional)
    issue_number = prompter.input_text(
        placeholder="Enter number or leave empty to skip",
        header="Issue/ticket number (optional):",
    )

    # Step 3: Branch description
    description = prompter.input_text(
        placeholder="Enter a short description of branch intent",
        header="Branch description:",
    )

    if not description:
        prompter.error(git_msg.DESCRIPTION_CAN_NOT_BE_EMPTY)
        raise prompter.exit(code=1)

    # Clean and format description
    description = sanitize_text(description)

    if not description:
        prompter.error(git_msg.DESCRIPTION_SANITATION_ERROR)
        raise prompter.exit(1)

    # Build branch name
    if issue_number:
        return f"{branch_type}/{issue_number}-{description}"
    else:
        return f"{branch_type}/{description}"


def _handle_forbidden_cross_repo_card(gh_project_item: Any, config: Any, repo_message: str) -> None:
    """Handle the forbidden cross-repository card scenario by displaying a valid message and exiting.

    Args:
        gh_project_item: The GitHub project item.
        config: The configuration object.
        repo_message: The raw repository message.
    """
    # Prefer a concise, user-friendly message using centralized text.
    try:
        # Derive the expected and actual repo labels for the message.
        expected = f"{getattr(config.github, 'owner', '')}/{getattr(config.github, 'repo', '')}"
        actual = None

        content = getattr(gh_project_item, "content", None) or {}
        if isinstance(content, dict):
            actual = content.get("repository") or None

        if not actual and gh_project_item.repository:
            repo_url = str(gh_project_item.repository)
            if "github.com/" in repo_url:
                parts = repo_url.rstrip("/").split("github.com/")[-1].split("/")
                if len(parts) >= 2:
                    actual = f"{parts[0]}/{parts[1]}"

        if not actual:
            actual = "<unknown>"

        prompter.error(
            msg.CROSS_REPO_CARD_FORBIDDEN.format(actual, expected),
        )
        raise prompter.exit(code=1)
    except Exception:
        prompter.error(repo_message)
        raise prompter.exit(code=1)


def register(app: typer.Typer) -> Dict[str, Callable[..., Any]]:
    """Register branch commands.

    Args:
        app: Typer application instance.

    Returns:
        Dictionary mapping command names to their functions.
    """

    @app.command()
    @ensure_git_repo()
    def check_branch(
        branch: str,
        config: Config = Depends(load_config),
    ):
        """Validate branch naming convention."""
        prompter.header("Validate branch")
        is_valid, message = validate_branch(branch, config.branch)
        if is_valid:
            prompter.success(message)
        else:
            prompter.error(message)
            raise prompter.exit(code=1)

    @app.command()
    @ensure_git_repo()
    def create_branch(
        branch_name: Optional[str] = typer.Argument(
            None, help="Branch name (if not provided, interactive mode)"
        ),
        project: Optional[str] = typer.Option(
            None, "--project", "-p", help="Project to extract the information from"
        ),
        issue: Optional[int] = typer.Option(
            None, "--issue", "-i", help="Issue to extract the information from"
        ),
        for_staging: bool = typer.Option(
            False, "--for-staging", "-fs", help="Create staging branch based on current branch"
        ),
        skip_checks: bool = typer.Option(
            False, "--skip-checks", help="Skip repository state validation"
        ),
        config: Config = Depends(get_config),
    ):
        """Create a new Git branch with validation (interactive mode)."""
        prompter.header("Create branch")

        # Validate repository state before creating branch
        if not skip_checks and at_least_one_validation_repo_state_set(config):
            with yaspin(text="Checking repository state...") as spinner:
                is_valid, messages = validate_repo_state(
                    check_uncommitted=config.validation.check_uncommitted,
                    check_behind=config.validation.check_behind_remote,
                    warn_only=config.validation.warn_only,
                )
                spinner.ok("✔")
                spinner.stop()

            if not is_valid:
                display_repo_state_issues(messages, warn_only=False)
                raise prompter.exit(code=1)

        # Determine branch name from different sources
        project_number = None
        if for_staging:
            current_branch = get_current_branch()
            final_branch_name = create_staging_branch_name(current_branch)
            prompter.info(f"Creating staging branch from: {current_branch}")
        elif branch_name:
            final_branch_name = branch_name
        elif issue or project:
            selected_project: str | list[str] | None = str(project)
            if not project:
                available_projects = [k for k, _ in config.github.projects.items()]
                if not available_projects:
                    prompter.error("No projects found.")
                    raise prompter.exit(1)

                selected_project = prompter.choose(
                    options=available_projects,
                    header="Choose a project:",
                )

            if not selected_project or isinstance(selected_project, list):
                prompter.error(msg.INVALID_CHOICE)
                raise prompter.exit(1)

            owner, project_number = resolve_project_number(project=selected_project)

            selected_issue = issue
            if not issue:
                items = _fetch_project_items(owner, project_number)
                issue_data = _get_issue_and_status_interactively(items)
                selected_issue = int(issue_data.get("issue", 0))
                issue = selected_issue

            with yaspin(text="Extracting information from issue"):
                assert isinstance(selected_issue, int)
                gh_project_item = find_project_item_for_issue(
                    owner=owner, project_number=project_number, issue=int(selected_issue)
                )

            # Optional rule: forbid creating branches for cards/issues that belong
            # to a different repository than the one configured for this project.
            if config.branch.forbid_cross_repo_cards:
                is_same_repo, repo_message = validate_cross_repo_card(
                    gh_project_item, config.github
                )

                if not is_same_repo:
                    _handle_forbidden_cross_repo_card(gh_project_item, config, repo_message)

            scope = detect_scope(config=config, project_item=gh_project_item)
            final_branch_name = resolve_issue_branch(
                scope=scope, project_item=gh_project_item, issue=selected_issue
            )
        else:
            final_branch_name = _get_branch_name_interactive(config)

        # Validate branch name
        with yaspin(text=f"Validating branch name: {final_branch_name}") as spinner:
            is_valid, message = validate_branch(final_branch_name, config.branch)
            spinner.ok("✔")

        if not is_valid:
            prompter.error(message)
            raise prompter.exit(1)

        prompter.success("Branch name is valid!")

        # Enforce one-branch-per-issue-per-environment rule when enabled
        if config.branch.enforce_single_branch_per_issue_env:
            existing_branches = get_existing_branches()
            is_unique, uniqueness_message = validate_single_branch_per_issue_env(
                final_branch_name, existing_branches
            )
            if not is_unique:
                prompter.error(uniqueness_message)
                raise prompter.exit(1)

        # Check if branch already exists and handle it
        handle_existing_branch(final_branch_name)

        # Confirm creation
        prompter.info(f"Ready to create branch: {final_branch_name}")
        if not prompter.confirm("Create and checkout?", default=True):
            prompter.info("Cancelled.")
            raise prompter.exit(0)

        # Store the mapping for future use
        if project_number and issue:
            mapping_manager = get_issue_mapping_manager()
            mapping_manager.add_mapping(int(issue), final_branch_name, project_number)

        # Create and checkout branch
        # TODO: complete branch linking
        # if issue:
        #     link_branch_to_issue(issue, final_branch_name)
        #     checkout_branch(final_branch_name)
        # else:
        create_and_checkout_branch(final_branch_name)

    @app.command()
    @ensure_git_repo()
    def list_owned_branches():
        """Show all local Git branches owned by the current user."""
        prompter.header("List owned branches")
        try:
            branches = list_user_owned_branches()
        except RuntimeError as e:
            prompter.error(str(e))
            raise prompter.exit(code=1)

        if not branches:
            prompter.warning(msg.NO_BRANCHES_OWNED_BY_YOU)
            raise prompter.exit(code=0)

        prompter.info("Branches owned by you:")
        for b in branches:
            prompter.indented_message(f"- {b}")

    @app.command()
    @ensure_git_repo()
    def delete_branch(
        branch: Optional[str] = typer.Argument(
            None, help="Name of the branch to delete (omit for interactive mode)"
        ),
        remote: str = typer.Option("origin", "--remote", "-r", help="Remote name"),
        force: bool = typer.Option(False, "--force", "-f", help="Force delete even if not merged"),
    ):
        """Delete a branch locally and on the remote, enforcing ownership rules."""
        prompter.header("Delete branch")
        # Load owned branches first (used for interactive and validation)
        try:
            owned_branches = list_user_owned_branches()
        except RuntimeError as e:
            prompter.error(str(e))
            raise prompter.exit(1)

        if not owned_branches:
            prompter.warning(msg.NO_OWNED_BRANCHES_TO_DELETE)
            raise prompter.exit(0)

        # Interactive selection if branch not provided
        branches = [branch] if branch else []
        if not branches:
            branches = prompter.choose(
                options=owned_branches,
                header=msg.SELECT_BRANCHES_TO_DELETE,
                limit=0,
            )
            if not branches:
                prompter.warning(msg.INVALID_CHOICE)
                raise prompter.exit(0)

        # Basic safety: don't delete main shared branches through this command
        current_branch = get_current_branch()
        for selected_branch in branches:
            protected_branches = ("main", "master", "develop")
            is_release_branch = selected_branch.startswith("release/")
            if selected_branch in protected_branches or is_release_branch:
                prompter.error(
                    msg.REFUSING_TO_DELETE_SHARED_BRANCH.format(selected_branch),
                )
                raise prompter.exit(1)

            # Prevent deleting the currently checked-out branch
            if current_branch == selected_branch:
                prompter.error(msg.CANNOT_DELETE_CURRENT_BRANCH)
                raise prompter.exit(1)

            # Enforce ownership rules before allowing delete using the same logic
            if selected_branch not in owned_branches:
                prompter.error(
                    msg.NOT_ALLOWED_TO_DELETE_BRANCH.format(selected_branch),
                )
                raise prompter.exit(1)

        if branches:
            prompter.warning(msg.DELETE_BRANCHES_STATEMENT)
            messages = [f"{counter}. {b}" for counter, b in enumerate(branches, 1)]
            for message in messages:
                prompter.indented_message(f"{message}")

            confirmation = prompter.confirm(msg.CONFIRM_DELETE_BRANCHES)

            if not confirmation:
                prompter.error(msg.CANCELLED)
                raise prompter.exit(0)

            for selected_branch in branches:
                delete_branch_local_and_remote(selected_branch, remote, force)
        else:
            prompter.error(msg.NO_SELECTED_BRANCHES_TO_DELETE)

    @app.command()
    @ensure_git_repo()
    def delete_merged(
        remote: str = typer.Option("origin", "--remote", "-r", help="Remote name"),
    ):
        """Delete branches that have been merged into develop (interactive)."""
        prompter.header("Delete merged branches")

        # 1. Get branches merged into develop
        merged_branches = set(get_merged_branches(base_branch="develop"))

        if not merged_branches:
            prompter.warning(msg.NO_MERGED_BRANCHES)
            raise prompter.exit(0)

        # 2. Get owned branches
        try:
            owned_branches = set(list_user_owned_branches())
        except RuntimeError as e:
            prompter.error(str(e))
            raise prompter.exit(1)

        # 3. Intersect: Only delete merged branches that are owned by the user
        candidates = sorted(list(merged_branches.intersection(owned_branches)))

        # 4. Filter out protected branches and current branch
        current_branch = get_current_branch()
        final_candidates = []

        for b in candidates:
            if b in ("main", "master", "develop") or b.startswith("release/"):
                continue
            if b == current_branch:
                continue
            final_candidates.append(b)

        if not final_candidates:
            prompter.warning(msg.NO_OWNED_MERGED_BRANCHES)
            raise prompter.exit(0)

        delete_branches_selection = prompter.choose(
            header=msg.SELECT_BRANCHES_TO_DELETE,
            options=final_candidates,
            limit=0,
        )
        if not delete_branches_selection:
            prompter.warning("No branches selected for deletion.")
            raise prompter.exit(1)
        assert isinstance(delete_branches_selection, list)
        if not delete_branches_selection:
            prompter.warning("No branches selected for deletion.")
            raise prompter.exit(1)

        prompter.warning(msg.DELETE_BRANCHES_STATEMENT)
        for index, branch in enumerate(delete_branches_selection, start=1):
            prompter.indented_message(f"{index}. {branch}")

        response = prompter.confirm("Delete these branches?")

        if not response:
            prompter.error("Deletion cancelled.")
            raise prompter.exit(code=0)

        for b in delete_branches_selection:
            delete_branch_local_and_remote(b, remote, force=False, ignore_remote_error=True)

    @app.command(name="switch-branch")
    @ensure_git_repo()
    def switch_branch(
        _: Config = Depends(get_config),
        branch: str | None = typer.Option(None, "--branch", "-b", help="Branch name"),
    ):
        """Interactively switch to another branch (alias: sb)."""
        prompter.header("Switch branch")
        checkout_branch_interactive(branch)

    @app.command(name="create-integration-branch")
    @ensure_git_repo()
    def create_integration_branch(
        config: Config = Depends(get_config),
        prefix: str = typer.Option("custom", "--prefix", "-p", help="Branch name prefix"),
        skip_checks: bool = typer.Option(
            False, "--skip-checks", help="Skip repository state validation"
        ),
    ):
        """Create an integration branch by merging multiple branches together."""
        prompter.header("Create integration branch")
        check_repo_state(config, skip_checks)
        current_branch = get_current_branch()
        branches_to_integrate = _get_available_branches_to_integrate_with(current_branch)
        _confirm_integration(
            current_branch=current_branch, branches_to_integrate=branches_to_integrate
        )
        branch_name = _get_integration_branch_name(
            config=config, prefix=prefix, branches_to_integrate=branches_to_integrate
        )
        _perform_integration(
            new_branch=branch_name,
            current_branch=current_branch,
            branches_to_integrate=branches_to_integrate,
        )

    return {
        "check_branch": check_branch,
        "create_branch": create_branch,
        "list_owned_branches": list_owned_branches,
        "delete_branch": delete_branch,
        "delete_merged": delete_merged,
        "switch_branch": switch_branch,
        "create_integration_branch": create_integration_branch,
    }
