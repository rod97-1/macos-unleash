#!/usr/bin/env python3
"""Workstation launcher. Run without arguments for help."""

import sys

if sys.version_info < (3, 10):
    print("unleash requires Python 3.10 or newer.", file=sys.stderr)
    raise SystemExit(2)

from unleashlib.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
