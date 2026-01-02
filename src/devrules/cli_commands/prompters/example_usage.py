"""Example usage of the Prompter interface.

This module demonstrates how to use the prompter factory and concrete implementations.
"""

from devrules.cli_commands.prompters.factory import get_default_prompter


def example_basic_usage():
    """Example: Basic usage with factory."""
    # Get the best available prompter (singleton)
    prompter = get_default_prompter()

    # Confirm dialog
    if prompter.confirm("Do you want to continue?", default=True):
        prompter.success("Great! Continuing...")
    else:
        prompter.warning("Operation cancelled")

    # Single selection
    options = ["Option 1", "Option 2", "Option 3"]
    selected = prompter.choose(options, header="Select an option:")
    if selected:
        prompter.info(f"You selected: {selected}")

    # Multi-selection
    selected_multiple = prompter.choose(
        options,
        header="Select multiple options:",
        limit=0,  # 0 means unlimited
    )
    if selected_multiple:
        prompter.success(f"You selected: {', '.join(selected_multiple)}")

    # Text input
    name = prompter.input_text(
        placeholder="Enter your name",
        header="What's your name?",
        default="User",
    )
    if name:
        prompter.info(f"Hello, {name}!")

    # Multi-line input
    description = prompter.write(
        placeholder="Enter a description",
        header="Describe your project:",
    )
    if description:
        prompter.success("Description saved!")


def example_styled_output():
    """Example: Using styled output."""
    prompter = get_default_prompter()

    # Styled text
    title = prompter.style("Important Title", foreground=81, bold=True)
    print(title)

    # Convenience methods
    prompter.success("Operation completed successfully!")
    prompter.error("An error occurred!")
    prompter.warning("This is a warning!")
    prompter.info("Here's some information")


def example_filter():
    """Example: Using filter for fuzzy search."""
    prompter = get_default_prompter()

    # Large list of options
    branches = [
        "feature/user-authentication",
        "feature/payment-integration",
        "bugfix/login-error",
        "bugfix/payment-validation",
        "hotfix/security-patch",
    ]

    selected = prompter.filter_list(
        branches,
        placeholder="Search branches...",
        header="Select a branch:",
    )

    if selected:
        prompter.success(f"Selected branch: {selected}")


def example_force_strategy():
    """Example: Force a specific strategy."""
    from devrules.cli_commands.prompters.gum_prompter import GumPrompter
    from devrules.cli_commands.prompters.typer_prompter import TyperPrompter

    # Try to use Gum
    gum_prompter = GumPrompter()
    if gum_prompter.is_available():
        print("Using Gum prompter")
        gum_prompter.info("Gum is available!")
    else:
        print("Gum not available, using Typer")
        typer_prompter = TyperPrompter()
        typer_prompter.info("Using Typer fallback")


if __name__ == "__main__":
    print("=== Basic Usage ===")
    example_basic_usage()

    print("\n=== Styled Output ===")
    example_styled_output()

    print("\n=== Filter Example ===")
    example_filter()

    print("\n=== Force Strategy ===")
    example_force_strategy()
