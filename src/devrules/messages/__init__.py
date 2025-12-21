"""Centralized message constants for DevRules CLI.

This module provides a single source of truth for all user-facing messages,
making it easier to maintain consistency and support internationalization.
"""

from dataclasses import dataclass


@dataclass
class BranchMessages:
    """Messages related to branch operations."""

    # Info messages
    NO_BRANCHES_OWNED_BY_YOU = "No branches owned by you were found."
    NO_OWNED_BRANCHES_TO_DELETE = "No owned branches available to delete."
    NO_MERGED_BRANCHES = "No branches found that are merged into develop."
    NO_OWNED_MERGED_BRANCHES = (
        "No owned merged branches available to delete (filtered protected/current)."
    )
    NO_SELECTED_BRANCHES_TO_DELETE = "No branches were selected nor provided to be deleted"
    DELETE_BRANCHES_STATEMENT = "You are about to delete the following branches:"

    # Error messages
    INVALID_CHOICE = "✘ Invalid choice"
    REFUSING_TO_DELETE_SHARED_BRANCH = "✘ Refusing to delete shared branch '{}' via CLI."
    UNABLE_TO_DETERMINE_CURRENT_BRANCH = "✘ Unable to determine current branch"
    CANNOT_DELETE_CURRENT_BRANCH = "✘ Cannot delete the branch you are currently on."
    NOT_ALLOWED_TO_DELETE_BRANCH = (
        "✘ You are not allowed to delete branch '{}' because you do not own it."
    )
    CROSS_REPO_CARD_FORBIDDEN = (
        "✘ Cannot create branch: the selected issue/card belongs to a different repository "
        "("
        "{}"
        " vs "
        "{}"
        ")."
    )

    # Prompts
    DELETE_BRANCH_PROMPT = "You are about to delete branch '{}' locally and from remote '{}'."
    CANCELLED = "Cancelled."


@dataclass
class CommitMessages:
    """Messages related to commit operations."""

    # Error messages
    MESSAGE_CANNOT_BE_EMPTY = "Message cannot be empty"
    NO_TAG_SELECTED = "No tag selected"
    INVALID_CHOICE = "✘ Invalid choice"
    COMMIT_MESSAGE_FILE_NOT_FOUND = "Commit message file not found: {}"
    FORBIDDEN_FILES_DETECTED = "✘ Forbidden Files Detected"
    CANNOT_COMMIT_TO_PROTECTED_BRANCH = (
        "✘ Cannot commit directly to '{}'. Branches containing '{}' are protected (merge-only)."
    )

    # Success messages
    COMMITTED_CHANGES = "✔ Committed changes!"

    # Info messages
    COMMIT_CANCELLED = "Commit cancelled"
    FAILED_TO_COMMIT_CHANGES = "✘ Failed to commit changes: {}"


@dataclass
class PRMessages:
    """Messages related to pull request operations."""

    # Error messages
    INVALID_PR_TARGET = "✘ Invalid PR Target"
    CURRENT_BRANCH_SAME_AS_BASE = (
        "✘ Current branch is the same as the base branch; nothing to create a PR for."
    )
    FAILED_TO_CREATE_PR = "✘ Failed to create PR: {}"

    # Success messages
    PR_CREATED_SUCCESSFULLY = "✔ PR created successfully!"

    # Info messages
    PR_CANCELLED = "PR cancelled"


@dataclass
class DeployMessages:
    """Messages related to deployment operations."""

    # Prompts
    CONFIRM_DEPLOYMENT = "¿Confirma que desea desplegar '{}' en '{}'?"
    DEPLOYMENT_CANCELLED = "Deployment cancelled."

    # Info messages
    DEPLOYING_TO_ENVIRONMENT = "🚀 Deploying {} to {}..."


@dataclass
class GitMessages:
    """Messages related to Git operations."""

    # Error messages
    NOT_A_GIT_REPOSITORY = "✘ Not a git repository"
    UNABLE_TO_DETERMINE_CURRENT_BRANCH = "✘ Unable to determine current branch"
    BRANCH_NAME_ALREADY_EXISTS = "\n✘ Branch '{}' already exists!"
    FAILED_TO_CREATE_BRANCH = "\n✘ Failed to create branch: {}"
    DESCRIPTION_CAN_NOT_BE_EMPTY = "✘ Description cannot be empty"


# Singleton instances for easy access
branch = BranchMessages()
commit = CommitMessages()
pr = PRMessages()
deploy = DeployMessages()
git = GitMessages()


# For backward compatibility and easy imports
__all__ = [
    "BranchMessages",
    "CommitMessages",
    "PRMessages",
    "DeployMessages",
    "GitMessages",
    "branch",
    "commit",
    "pr",
    "deploy",
    "git",
]
