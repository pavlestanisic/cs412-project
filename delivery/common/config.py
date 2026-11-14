"""Command-line configuration shared by both launch paths."""

import argparse
from pathlib import Path

DEFAULT_LOG_FILE = str(Path(__file__).resolve().parents[2] / "logs" / "app.log")


def parse_args(argv):
    """Read the command line options."""
    parser = argparse.ArgumentParser(description="Food delivery dispatch app")
    parser.add_argument("--menu", action="store_true", help="interactive menu instead of the demo")
    parser.add_argument("--dispatcher", choices=["nearest", "fastest"], default="nearest",
                        help="how couriers are chosen")
    parser.add_argument("--log-level", default="INFO", help="DEBUG, INFO, WARNING, ERROR")
    parser.add_argument("--log-file", default=DEFAULT_LOG_FILE, help="where to write logs")
    parser.add_argument("--log-console", action="store_true", help="also print logs to stderr")
    return parser.parse_args(argv)

