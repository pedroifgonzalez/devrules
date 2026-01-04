import subprocess

from devrules.core.rules_engine import rule


@rule(name="validate_docstrings", description="Validate docstrings in the code.")
def check_docstrings(path: str = "src") -> tuple[bool, str]:
    """Validate docstrings in the code.

    Example interrogate response:
        RESULT: PASSED (minimum: 80.0%, actual: 98.3%)

    """
    result = subprocess.run(["interrogate", path], capture_output=True, text=True)
    if "PASSED" in result.stdout:
        return True, f"Docstrings are valid in {path}."
    return False, f"Docstrings are invalid in {path}."
