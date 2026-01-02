import shutil
import subprocess
from typing import Optional

DINY_AVAILABLE = shutil.which("diny") is not None
DEFAULT_TIMEOUT = 30  # seconds


def is_available() -> bool:
    """Check if diny is installed and available."""
    return DINY_AVAILABLE


def generate_commit_message(timeout: int = DEFAULT_TIMEOUT) -> Optional[str]:
    """Generate a commit message using diny with timeout and error handling.

    Args:
        timeout: Maximum time to wait for diny to complete (default: 30 seconds)

    Returns:
        Generated commit message or None if generation failed

    Raises:
        None - all exceptions are caught and return None for graceful fallback
    """
    if not is_available():
        return None

    try:
        result = subprocess.run(
            ["diny", "commit", "--print"],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=True,
        )
        if result.returncode == 0:
            return result.stdout.strip()
        else:
            # stderr is included in result when check=False, but we use check=True
            # so CalledProcessError will be raised with stderr info
            return None
    except subprocess.TimeoutExpired:
        return None
    except subprocess.CalledProcessError:
        # Error includes stderr information for diagnostics
        return None
    except Exception:
        # Catch any other exceptions (network issues, etc.)
        return None
