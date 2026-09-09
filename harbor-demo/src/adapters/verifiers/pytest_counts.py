from __future__ import annotations

import re

_PASSED = re.compile(r"(\d+)\s+passed")
_FAILED = re.compile(r"(\d+)\s+failed")
_ERROR = re.compile(r"(\d+)\s+error")


def parse_pytest_counts(output: str) -> tuple[int, int]:
    """Extract passed/failed counts from pytest summary text."""
    passed = int(m.group(1)) if (m := _PASSED.search(output)) else 0
    failed = int(m.group(1)) if (m := _FAILED.search(output)) else 0
    errors = int(m.group(1)) if (m := _ERROR.search(output)) else 0
    return passed, failed + errors
