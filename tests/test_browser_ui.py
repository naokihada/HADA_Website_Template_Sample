#!/usr/bin/env python3
"""Real-browser UI contract entry point; requires the optional Playwright extra."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "core"))
from browser_contract import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main(["--root", str(Path(__file__).resolve().parents[1])]))
