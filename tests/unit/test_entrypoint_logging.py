import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from delivery.common.errors import ValidationError
from delivery.common.logging import setup_logging
from delivery.core.entrypoint import main


class EntrypointLoggingTestCase(unittest.TestCase):

    def test_startup_exception_is_logged_with_traceback(self):
        try:
            with tempfile.TemporaryDirectory() as directory:
                log_file = Path(directory) / "app.log"
                error = ValidationError("sample data failed")

                # The demo uses an in-memory database, so no file is touched.
                with patch("delivery.core.entrypoint.load_sample_data", side_effect=error):
                    with self.assertRaises(ValidationError):
                        main(["--log-file", str(log_file)])

                log_contents = log_file.read_text(encoding="utf-8")
                self.assertIn("Application failed", log_contents)
                self.assertIn("Traceback (most recent call last):", log_contents)
                self.assertIn("ValidationError: sample data failed", log_contents)
        finally:
            setup_logging("INFO", None, False)


if __name__ == "__main__":
    unittest.main()
