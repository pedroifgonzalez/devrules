import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from devrules.utils.dependencies import get_config


class TestGetConfig(unittest.TestCase):
    def test_get_config_with_custom_path(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write('[general]\nproject_name = "test_project"\n')
            config_path = Path(f.name)

        try:
            with patch("devrules.utils.dependencies.load_config") as mock_load:
                get_config(config_path)
                mock_load.assert_called_once_with(config_path)
        finally:
            config_path.unlink()

    def test_get_config_with_none_path(self):
        with patch("devrules.utils.dependencies.load_config") as mock_load:
            get_config(None)
            mock_load.assert_called_once_with(None)


if __name__ == "__main__":
    unittest.main()
