#!/usr/bin/env python3
"""Run United Agents server."""

import sys
sys.path.insert(0, '.')

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from src.main import run

if __name__ == "__main__":
    run()
