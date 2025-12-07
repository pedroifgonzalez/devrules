"""Interactive shell for DevRules - REPL-style interface."""

import shlex
import sys

from devrules.cli_commands import app
from devrules.utils import gum


def run_shell():
    """Run interactive DevRules shell."""
    if gum.is_available():
        print(gum.style("🚀 DevRules Interactive Shell", foreground=81, bold=True))
        print(
            gum.style(
                "Type commands without 'devrules' prefix. Type 'exit' or 'quit' to leave.",
                foreground=245,
            )
        )
        print(gum.style("=" * 60, foreground=81))
    else:
        print("🚀 DevRules Interactive Shell")
        print("Type commands without 'devrules' prefix. Type 'exit' or 'quit' to leave.")
        print("=" * 60)

    print()

    while True:
        try:
            # Get command input
            if gum.is_available():
                cmd = gum.input_text(
                    placeholder="create-branch, icommit, ipr, help...",
                    header="devrules>",
                )
                if cmd is None:
                    continue
            else:
                cmd = input("devrules> ").strip()

            if not cmd:
                continue

            # Exit commands
            if cmd.lower() in ("exit", "quit", "q"):
                print("\n👋 Goodbye!")
                break

            # Parse command and arguments
            try:
                args = shlex.split(cmd)
            except ValueError as e:
                print(f"Error parsing command: {e}")
                continue

            # Run the command through typer
            try:
                # Temporarily override sys.argv
                original_argv = sys.argv
                sys.argv = ["devrules"] + args

                try:
                    app(standalone_mode=False)
                except SystemExit:
                    # Typer raises SystemExit, we catch it to continue the shell
                    pass
                except Exception as e:
                    print(f"Error: {e}")
                finally:
                    sys.argv = original_argv

            except Exception as e:
                print(f"Error running command: {e}")

            # Add separator after each command
            print()
            if gum.is_available():
                print(gum.style("─" * 60, foreground=240))
            else:
                print("-" * 60)
            print()

        except KeyboardInterrupt:
            print("\n\n👋 Goodbye!")
            break
        except EOFError:
            print("\n👋 Goodbye!")
            break


if __name__ == "__main__":
    run_shell()
