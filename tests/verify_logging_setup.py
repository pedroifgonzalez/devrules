import sys
from io import StringIO
from pathlib import Path

from loguru import logger

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from devrules.config import LoggingConfig
from devrules.logging_setup import configure_logging


def test_configure_logging():
    print("Testing configure_logging with Loguru...")

    class MockConfig:
        def __init__(self, enabled, level, fmt=None):
            self.logging = LoggingConfig(enabled=enabled, level=level, format=fmt)

    # Helper to capture stderr
    class Capture(list):
        def __enter__(self):
            self._original_stderr = sys.stderr
            self._stringio = StringIO()
            sys.stderr = self._stringio
            return self

        def __exit__(self, *args):
            self.extend(self._stringio.getvalue().splitlines())
            sys.stderr = self._original_stderr

    # Test Case 1: Disabled
    print("  Case 1: Logging disabled")
    config = MockConfig(enabled=False, level="INFO")
    configure_logging(config)

    with Capture() as output:
        logger.info("This should not be logged")
        logger.error("This should also not be logged (disabled)")

    if len(output) > 0:
        print(f"FAILED: Expected no output, got: {output}")
        sys.exit(1)
    print("  PASSED")

    # Test Case 2: Enabled (DEBUG)
    print("  Case 2: Logging enabled (DEBUG)")
    config = MockConfig(enabled=True, level="DEBUG")
    configure_logging(config)

    with Capture() as output:
        logger.debug("Debug message")
        logger.info("Info message")

    if len(output) < 2:
        print(f"FAILED: Expected at least 2 log lines, got {len(output)}")
        sys.exit(1)

    if "Debug message" not in output[0] and "Debug message" not in output[1]:
        print(f"FAILED: Expected 'Debug message' in output, got: {output}")
        sys.exit(1)

    print("  PASSED")
    print("\nAll unit tests passed!")


if __name__ == "__main__":
    test_configure_logging()
