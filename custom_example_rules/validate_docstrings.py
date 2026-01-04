import subprocess

from devrules.core.enum import DevRulesEvent
from devrules.core.rules_engine import rule


@rule(
    name="validate_docstrings",
    description="Validate docstrings in the code.",
    hooks=[DevRulesEvent.PRE_COMMIT],
    ignore_defaults=True,
)
def check_docstrings(path: str = "src", fail_under: int = 98) -> tuple[bool, str]:
    """Validate docstrings in the code.

    Example interrogate response:
        RESULT: PASSED (minimum: 80.0%, actual: 98.3%)

    """
    if ".." in path or path.startswith("/"):
        return False, f"Error: Invalid path '{path}'. Must be a relative path within the project."

    try:
        result = subprocess.run(
            ["interrogate", path, "--fail-under", str(fail_under)],
            capture_output=True,
            text=True,
            check=False,
        )
        valid = "PASSED" in result.stdout
        return valid, result.stdout
    except FileNotFoundError:
        return (
            False,
            "Error: interrogate is not installed. Install it with: pip install interrogate",
        )
    except Exception as e:
        return False, f"Error running interrogate: {str(e)}"
