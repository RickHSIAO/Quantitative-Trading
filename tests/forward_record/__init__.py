from __future__ import annotations

import unittest
from pathlib import Path


def load_tests(loader: unittest.TestLoader, tests: unittest.TestSuite, pattern: str | None) -> unittest.TestSuite:
    return loader.discover(str(Path(__file__).parent), pattern or "test*.py")
