#!/usr/bin/env bash
# Run only inside a disposable root-owned test container with the checkout at /repo.
set -euo pipefail
if [[ ! -f /.dockerenv || "$(id -u)" != 0 ]]; then
    echo 'This test installs packages. Run it only in a disposable Docker container as root.' >&2
    exit 2
fi
cd /repo
export PYTHONDONTWRITEBYTECODE=1
if command -v apt-get >/dev/null 2>&1; then
    if [[ -n "${UNLEASH_TEST_CA:-}" ]]; then
        printf 'Acquire::https::CaInfo "%s";\n' "$UNLEASH_TEST_CA" > /etc/apt/apt.conf.d/99-unleash-test-ca
    fi
    apt-get update
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends python3 ca-certificates
elif command -v dnf >/dev/null 2>&1; then
    if [[ -n "${UNLEASH_TEST_CA:-}" ]]; then
        printf '\nsslcacert=%s\n' "$UNLEASH_TEST_CA" >> /etc/dnf/dnf.conf
    fi
    dnf install -y --setopt=install_weak_deps=False python3 ca-certificates
else
    echo 'No supported package manager.' >&2
    exit 2
fi
python3 -m unittest discover -s tests -v
python3 unleash.py doctor
python3 unleash.py plan --profile core --profile dev --state-dir /tmp/unleash-integration-state
[[ ! -e /tmp/unleash-integration-state ]]
python3 unleash.py apply --profile core --profile dev --state-dir /tmp/unleash-integration-state
python3 unleash.py status --profile core --profile dev
python3 unleash.py apply --profile core --profile dev --state-dir /tmp/unleash-integration-state | tee /tmp/unleash-second-apply.log
grep -q 'Installed and verified 0 tool(s)' /tmp/unleash-second-apply.log
[[ ! -e /tmp/unleash-integration-state ]]
echo 'PASS: native core/dev install, status, repeat apply, and mutation-free planning.'
