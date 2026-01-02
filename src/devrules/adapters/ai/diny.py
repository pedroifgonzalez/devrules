import shutil
import subprocess

DINY_AVAILABLE = shutil.which("diny") is not None


def is_available() -> bool:
    """Check if diny is installed and available."""
    return DINY_AVAILABLE


def generate_commit_message() -> str:
    """Generate a commit message using diny."""
    if not is_available():
        raise Exception("diny is not installed")
    try:
        result = subprocess.run(["diny", "commit", "--print"], capture_output=True, text=True)
        if result.returncode == 0:
            return result.stdout.strip()
        else:
            raise Exception(f"diny failed with error code {result.returncode}")
    except Exception as e:
        raise e
