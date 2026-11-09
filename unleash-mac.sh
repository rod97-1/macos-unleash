#!/usr/bin/env bash
# Compatibility entry point. Python handles selection, planning, and recovery.
set -euo pipefail
if [[ "$(uname -s)" != Darwin || "$(uname -m)" != arm64 ]]; then
    echo 'This entry point requires native Apple Silicon macOS. On Linux use python3 unleash.py.' >&2
    exit 2
fi
if ! command -v python3 >/dev/null 2>&1; then
    echo 'Python 3.10 or newer is required. Install it before running this launcher.' >&2
    exit 2
fi
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$SCRIPT_DIR/unleash.py" "$@"
