from __future__ import annotations

import sys
from pathlib import Path


def pytest_configure() -> None:
    api_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(api_root))
