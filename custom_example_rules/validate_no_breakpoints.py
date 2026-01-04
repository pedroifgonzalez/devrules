import re
import subprocess

from devrules.core.enum import DevRulesEvent
from devrules.core.rules_engine import rule


@rule(
    name="validate_no_breakpoints",
    description="Validate that there are no breakpoints in the code.",
    hooks=[DevRulesEvent.PRE_COMMIT],
    ignore_defaults=True,
)
def validate_no_breakpoints() -> tuple[bool, str]:
    """Check for debugging statements in staged changes and report file paths."""

    patterns = [
        r"\bbreakpoint\(\)",
        r"\bpdb\.set_trace\(\)",
        r"\bipdb\.set_trace\(\)",
        r"\bimport\s+pdb\b",
        r"\bimport\s+ipdb\b",
        r"\bdebugger\b;?",
        r"\bconsole\.log\(",
        r"\bbinding\.pry\b",
        r"\bbyebug\b",
    ]

    combined = re.compile("|".join(patterns))

    try:
        diff = subprocess.run(
            ["git", "diff", "--cached", "--unified=0"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout

        offending: dict[str, list[str]] = {}
        current_file: str | None = None

        for line in diff.splitlines():
            # Detect file from diff header
            if line.startswith("+++ b/"):
                current_file = line[6:]
                continue

            # Only added lines (ignore diff metadata)
            if current_file and line.startswith("+") and not line.startswith("+++"):
                content = line[1:]
                if combined.search(content):
                    offending.setdefault(current_file, []).append(content.strip())

        if offending:
            msg = "Debugging statements detected in staged changes:\n\n"

            for file, lines in offending.items():
                msg += f"{file}\n"
                for line in lines[:5]:
                    msg += f"  • {line}\n"
                if len(lines) > 5:
                    msg += f"  ... and {len(lines) - 5} more\n"
                msg += "\n"

            msg += "💡 Remove debugging statements before committing."
            return False, msg

        return True, "No debugging statements found in staged changes."

    except (subprocess.CalledProcessError, OSError) as exc:
        return False, f"Error checking staged diff: {exc}"
