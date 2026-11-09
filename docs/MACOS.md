# Apple Silicon macOS setup

The Python launcher replaces the old Bash-only bootstrap. Homebrew and Python 3.10 or newer must already be installed. It no longer installs Homebrew from a downloaded script, rewrites your shell profile, tunes the system automatically, or installs a persistent boot daemon.

## Prerequisites

Confirm a native Apple Silicon session and developer tools:

```bash
uname -s
uname -m
xcode-select -p
python3 --version
brew --version
```

The platform checks require `Darwin` and `arm64`. Intel Macs and Python running under Rosetta are rejected. If needed, use Apple's `xcode-select --install` and [Homebrew's official installation instructions](https://docs.brew.sh/Installation) separately.

If your existing Python is too old, Homebrew can install Python 3.12:

```bash
brew install python@3.12
export PATH="$(brew --prefix python@3.12)/libexec/bin:$PATH"
python3 --version
```

This PATH change applies only to the current shell unless you choose to save it yourself. Run Homebrew and the launcher as your normal account.

## Tools

```bash
python3 unleash.py doctor
python3 unleash.py plan --profile core --profile dev
python3 unleash.py apply --profile core --profile dev
python3 unleash.py status --profile core --profile dev
```

Use `--profile full` to select the original 31 Brewfile entries. The launcher verifies formula and cask installation through Homebrew. `Brewfile` remains usable with `brew bundle --file=Brewfile` independently; this installs packages only and does not create launcher recovery state.

The familiar entry point delegates to the launcher:

```bash
bash unleash-mac.sh plan --profile core
```

Calling it with no arguments shows help. It no longer applies settings merely because the script was launched. Claude Code is now a separate manual tool selection, not an unconditional post-install npm action.

## Migrating an existing boot daemon

The old script created `/Library/LaunchDaemons/com.custom.unleash.plist`. The new launcher refuses tuning while that file exists because it can reapply old wireless/GPU settings after recovery.

Inspect it before making changes:

```bash
plutil -lint /Library/LaunchDaemons/com.custom.unleash.plist
sudo launchctl print system/com.custom.unleash
```

Preserve a copy if you may need it. When you have confirmed it is the daemon installed by this project, unload it:

```bash
sudo launchctl bootout system /Library/LaunchDaemons/com.custom.unleash.plist
```

If it is already unloaded, confirm that through launchctl. Resolve other errors rather than suppressing them. Remove only the confirmed project daemon after unloading:

```bash
sudo rm /Library/LaunchDaemons/com.custom.unleash.plist
```

Unloading or deleting the file does not reverse settings it already applied. Follow the legacy recovery notes in [troubleshooting](TROUBLESHOOTING.md#legacy-mac-recovery). Original values from the Bash-only script were not saved and cannot be reconstructed automatically.

## Explicit settings

Preview before applying. Each group is a separate choice; no group is implied by a tool profile.

| Option | Effect |
| --- | --- |
| `--tune desktop` | Dock timing and animations, Finder animations, global animation/App Nap preferences, and keyboard repeat. |
| `--tune power` | Set charger sleep to zero and charger display sleep to 20 minutes. Preserve battery settings. |
| `--tune services` | Set disabling overrides for analyticsd and diagnosticd, and disable Bonjour advertising. Does not prove all telemetry is disabled or stop already running services. |
| `--tune wireless` | Bring down awdl0 and llw0 for this session. This affects AirDrop and nearby-device features. Nothing is added to boot. |
| `--gpu-limit-mb VALUE` | Set the OS-specific GPU wired limit explicitly, if supported. No allocation is inferred from machine size. |

GPU input must be positive and leave at least 4 GiB and 20 percent of physical memory outside the requested wired limit. This bound is a guardrail, not evidence that a chosen workload is safe or faster. The original limit is recorded before applying a new one. GPU and wireless settings are not made persistent across reboot.

Selected setting values are read before changes and checked afterward. Some preferences need an application restart or sign-out; the launcher does not terminate Dock or Finder. Native macOS tuning still requires verification on a suitable Mac. Unit tests cover command behavior and recovery, not macOS performance.

## Recovery

```bash
python3 unleash.py restore
```

State is stored under `~/Library/Application Support/macos-unleash` with user-only permissions. Restore checks for external changes first. A missing original preference is restored by removing the new override; recorded original values retain their types.

Service recovery restores the recorded enabled/disabled override state. It does not guarantee a service starts immediately, nor remove every historical launchd override entry. Installed applications, shell changes made by older installers, models, and prior Bash-only modifications are outside launcher recovery.
