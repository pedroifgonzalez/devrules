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
    """Check for common debugging breakpoints in staged files.

    Detects:
    - Python: breakpoint(), pdb.set_trace(), ipdb.set_trace()
    - JavaScript/TypeScript: debugger;
    - Ruby: binding.pry, byebug
    """
    # Common breakpoint patterns across languages
    breakpoint_patterns = [
        r"\bbreakpoint\(\)",  # Python 3.7+
        r"\bpdb\.set_trace\(\)",  # Python pdb
        r"\bipdb\.set_trace\(\)",  # Python ipdb
        r"\bimport\s+pdb",  # Python pdb import
        r"\bimport\s+ipdb",  # Python ipdb import
        r"\bdebugger;",  # JavaScript/TypeScript
        r"\bconsole\.log\(",  # JavaScript console.log (optional)
        r"\bbinding\.pry",  # Ruby pry
        r"\bbyebug",  # Ruby byebug
    ]

    # Get staged files
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            capture_output=True,
            text=True,
            check=True,
        )
        staged_files = [f.strip() for f in result.stdout.split("\n") if f.strip()]

        if not staged_files:
            return True, "No staged files to check."

        # Check each pattern in staged files
        found_breakpoints = []
        for pattern in breakpoint_patterns:
            grep_result = subprocess.run(
                ["git", "grep", "-n", "-E", pattern, "--cached"],
                capture_output=True,
                text=True,
            )

            if grep_result.returncode == 0:
                # Found matches
                matches = grep_result.stdout.strip().split("\n")
                found_breakpoints.extend(matches)

        if found_breakpoints:
            error_msg = "❌ Breakpoints detected in staged files:\n\n"
            for match in found_breakpoints[:10]:  # Limit to first 10
                error_msg += f"  • {match}\n"
            if len(found_breakpoints) > 10:
                error_msg += f"\n  ... and {len(found_breakpoints) - 10} more"
            error_msg += "\n💡 Remove debugging statements before committing."
            return False, error_msg

        return True, f"✓ No breakpoints found in {len(staged_files)} staged file(s)."

    except subprocess.CalledProcessError as e:
        return False, f"Error checking for breakpoints: {e}"
