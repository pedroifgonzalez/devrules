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
    result = subprocess.run(
        ["interrogate", path, "--fail-under", str(fail_under)], capture_output=True, text=True
    )
    valid = "PASSED" in result.stdout
    return valid, result.stdout
