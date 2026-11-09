# Linux setup

The launcher supports Ubuntu, Debian, and Fedora through their native package managers. It uses Python 3.10 or newer and no third-party Python modules. The first native package integration targets are Ubuntu 24.04, Debian 13, and Fedora 44 on x86_64. Linux arm64 detection is supported, but native arm64 installation has not been exercised by this release's integration checks.

## Prerequisites

Use a supported release with working official repositories. On Ubuntu or Debian, install the launcher prerequisites if absent:

```bash
sudo apt-get update
sudo apt-get install python3 git ca-certificates
```

On Fedora:

```bash
sudo dnf install python3 git ca-certificates
```

Run the launcher as your normal user. Package installation requests sudo when needed. Do not run user-session tuning through `sudo python3`.

## Core and development tools

From the checkout:

```bash
python3 unleash.py doctor
python3 unleash.py plan --profile core --profile dev
python3 unleash.py apply --profile core --profile dev
python3 unleash.py status --profile core --profile dev
```

APT refreshes repository metadata before checking availability and installing missing packages with recommendations disabled. DNF resolves native providers, including virtual package names, and disables weak dependencies. Neither adapter upgrades the entire system. Distribution package versions are used; the Mac Python 3.12 formula does not impose Python 3.12 on Linux.

A second apply verifies installed package records and skips tools already present. Executables installed outside the native package manager do not automatically satisfy a mapped package selection.

## Tool availability

| Selection | Linux behavior |
| --- | --- |
| `core`, `dev` | Distribution packages on all three supported families. |
| `desktop` | Syncthing and VLC use native packages. Firefox ESR uses Debian's repository, Fedora uses its Firefox package, and Ubuntu Firefox is a manual prerequisite to avoid implicitly installing Snap. |
| `ai` / `ollama` | An existing `ollama` command is required. Follow [Ollama's official Linux guide](https://docs.ollama.com/linux) separately. |
| `uv`, `bun` | Existing commands are recognized; follow the tools' official installation instructions separately. |
| `claude` | Existing `claude` command is recognized; install and authenticate separately using [the official guide](https://code.claude.com/docs/en/setup). |
| Mac applications | No invented Linux equivalent. Entries without a mapping or executable check are reported as manual prerequisites. |

For example, use `--profile desktop --exclude firefox` when Firefox is managed separately. The full Mac profile is available for inspection but is not a portable Linux software collection.

The launcher does not execute external installer scripts, add vendor repositories, accept unsigned packages, or fetch AI models. If a manually installed optional executable is present, status confirms command availability, not authentication, model availability, or end-to-end AI service health.

## Desktop and power settings

Tuning is optional and separate from tool profiles:

```bash
python3 unleash.py plan --no-packages --tune desktop
python3 unleash.py apply --no-packages --tune desktop
```

Desktop tuning requires GNOME, a writable `org.gnome.desktop.interface enable-animations` key, and an active D-Bus user session. KDE, headless servers, and desktop configurations without that schema are not silently modified.

`--tune power` requires `powerprofilesctl` and an advertised performance profile. Systems exposing only balanced and power-saver profiles are rejected. The launcher does not install or replace power-management services, disable wireless, change GPU memory, write kernel parameters, or disable security controls on Linux.

The current cloud host and package containers do not provide a real desktop or physical power profiles. Those tuning paths have command-fixture and recovery tests, not a native desktop validation claim.

## Recovery

```bash
python3 unleash.py restore
```

State uses a private directory under `XDG_STATE_HOME`, or `~/.local/state` when that variable is unset. `--state-dir` overrides it. Preserve this directory until you no longer need recovery. A journal belongs to one user, platform, and architecture; do not copy it between machines and expect safe restoration.

Recovery checks current values before writing and stops on conflicts. It restores only recorded settings, not package installation or earlier actions outside the launcher.
