"""Quick verification test for prompter implementations."""

import sys
from pathlib import Path

# Add src to path for imports
try:
    from devrules.cli_commands.prompters.factory import get_default_prompter, get_prompter
    from devrules.cli_commands.prompters.gum_prompter import GumPrompter
    from devrules.cli_commands.prompters.typer_prompter import TyperPrompter
except ModuleNotFoundError:
    # Add src to path for imports when running directly from source tree
    src_path = str(Path(__file__).resolve().parent.parent.parent.parent)
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

from devrules.cli_commands.prompters.factory import get_default_prompter, get_prompter
from devrules.cli_commands.prompters.gum_prompter import GumPrompter
from devrules.cli_commands.prompters.typer_prompter import TyperPrompter


def test_abstract_methods():
    """Verify all abstract methods are implemented."""
    print("Testing abstract method implementation...")

    # Check GumPrompter
    gum = GumPrompter()
    required_methods = [
        "is_available",
        "confirm",
        "choose",
        "input_text",
        "write",
        "filter_list",
        "style",
        "print_styled",
        "success",
        "error",
        "warning",
        "info",
    ]

    for method in required_methods:
        assert hasattr(gum, method), f"GumPrompter missing {method}"
        assert callable(getattr(gum, method)), f"GumPrompter.{method} not callable"

    # Check TyperPrompter
    typer_prompter = TyperPrompter()
    for method in required_methods:
        assert hasattr(typer_prompter, method), f"TyperPrompter missing {method}"
        assert callable(getattr(typer_prompter, method)), f"TyperPrompter.{method} not callable"

    print("✅ All abstract methods implemented")


def test_availability():
    """Test availability checks."""
    print("\nTesting availability...")

    gum = GumPrompter()
    typer_prompter = TyperPrompter()

    # Typer should always be available
    assert typer_prompter.is_available(), "TyperPrompter should always be available"

    # Gum availability depends on installation
    gum_available = gum.is_available()
    print(f"  Gum available: {gum_available}")
    print(f"  Typer available: {typer_prompter.is_available()}")

    print("✅ Availability checks working")


def test_factory():
    """Test factory pattern."""
    print("\nTesting factory pattern...")

    # Get prompter
    prompter = get_prompter()
    assert prompter is not None, "Factory should return a prompter"

    # Get default (singleton)
    prompter1 = get_default_prompter()
    prompter2 = get_default_prompter()
    assert prompter1 is prompter2, "get_default_prompter should return singleton"

    print(f"  Factory returned: {type(prompter).__name__}")
    print("✅ Factory pattern working")


def test_type_hints():
    """Verify type hints are present."""
    print("\nTesting type hints...")

    from typing import get_type_hints

    gum = GumPrompter()

    # Check a few key methods have type hints
    confirm_hints = get_type_hints(gum.confirm)
    assert "message" in confirm_hints, "confirm should have message type hint"
    assert "return" in confirm_hints, "confirm should have return type hint"

    choose_hints = get_type_hints(gum.choose)
    assert "options" in choose_hints, "choose should have options type hint"

    print("✅ Type hints present")


def test_message_methods():
    """Test message output methods (non-interactive)."""
    print("\nTesting message methods...")

    prompter = TyperPrompter()  # Use Typer to avoid gum dependency

    # These should not raise exceptions
    try:
        prompter.success("Test success")
        prompter.error("Test error")
        prompter.warning("Test warning")
        prompter.info("Test info")
        print("✅ Message methods working")
    except Exception as e:
        print(f"❌ Message methods failed: {e}")
        raise


def main():
    """Run all tests."""
    print("=" * 60)
    print("Prompter Implementation Verification")
    print("=" * 60)

    try:
        test_abstract_methods()
        test_availability()
        test_factory()
        test_type_hints()
        test_message_methods()

        print("\n" + "=" * 60)
        print("✅ All verification tests passed!")
        print("=" * 60)
        return 0
    except Exception as e:
        print(f"\n❌ Verification failed: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
