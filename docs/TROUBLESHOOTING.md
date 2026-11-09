# Troubleshooting

Run diagnostic and recovery commands on the affected Mac. The script has no automatic rollback, and rerunning it reapplies system changes before reaching software installation.

## Find the failing step

The script prints five numbered stages. Record the last stage, the failing command, and its error text. Avoid sharing a full `system_profiler` report, which can include identifying hardware details.

These commands provide basic context:

```bash
sw_vers -productVersion
uname -m
bash --version
```

Inspect output for personal information before posting it. Report problems through the [repository issues](https://github.com/rod97-1/macos-unleash/issues), including the stage and whether earlier changes were applied.

## Common problems

| Symptom | Likely cause | Next step |
| --- | --- | --- |
| `system_profiler: command not found` | Running outside macOS, or a modified PATH | Confirm `uname -s` reports `Darwin`. This script cannot configure Linux or Windows. |
| Apple Silicon Mac reports `x86_64` | Terminal may be running through Rosetta | Open a native terminal and confirm `uname -m` reports `arm64`. |
| Command Line Tools missing | Homebrew prerequisites are absent | Run `xcode-select --install`, finish the installer, then check `xcode-select -p`. |
| `sudo` authentication fails | Incorrect password or account lacks administrator access | Use an authorized administrator account. Do not run the entire script using `sudo bash`. |
| AirDrop or nearby device features stop working | The boot daemon brings down `awdl0` and `llw0` | Follow wireless recovery below. Restarting alone can reapply the change. |
| Local device discovery changes | Bonjour advertising preference was changed | Follow Bonjour recovery below. |
| `Bootstrap failed` | Invalid plist, service state, or launchd permissions | Use the launch daemon checks below. Do not assume its commands ran. |
| `unknown oid` for `iogpu.wired_limit_mb` | The current OS does not expose that key | Do not substitute an unrelated kernel setting. Use daemon recovery to stop applying this configuration. |
| `pmset` rejects an option | Unsupported hardware or macOS option | Inspect `pmset -g cap` and `pmset -g custom`. Earlier changes may already be applied. |
| `brew: command not found` after installation | Homebrew is missing from PATH | On a standard Apple Silicon install, confirm `/opt/homebrew/bin/brew` exists, then run `eval "$(/opt/homebrew/bin/brew shellenv)"`. |
| Homebrew package or cask fails | Network failure, unavailable package, disk space, or application conflict | Read the specific error, run `brew doctor`, then retry only software installation as shown below. |
| npm reports a permission error | Its global prefix is not writable | Inspect `npm config get prefix`. Use a user-writable Node installation or prefix following npm's documentation. Avoid `sudo npm install`. |
| Memory pressure under load | Workload may exceed available memory; the daemon may have raised the wired limit | Stop the workload, inspect Activity Monitor, and use GPU recovery below. |

## Check the launch daemon

```bash
plutil -lint /Library/LaunchDaemons/com.custom.unleash.plist
ls -l /Library/LaunchDaemons/com.custom.unleash.plist
sudo launchctl print system/com.custom.unleash
```

The script sets ownership to `root:wheel` and permissions to `644`. A valid plist and successful bootstrap do not prove every command succeeded. Its commands use semicolons, so an earlier failure can be hidden by the final command's exit status. Inspect interface flags and the GPU limit directly.

## Retry software installation

From the repository directory, after resolving the reported Homebrew error:

```bash
brew bundle --file=Brewfile
brew bundle check --file=Brewfile
```

This retries package installation without reapplying system changes. It does not retry the separate npm installation. If you want Claude Code, check your Node and npm installation before running:

```bash
npm install -g @anthropic-ai/claude-code
```

Package versions are not locked. A later run may behave differently even when this repository has not changed.

## Recovery

Recovery is partial because the script does not record previous values. Removing its boot daemon does not undo preferences, service overrides, power settings, or installed software.

Before a first run, save a system backup and record values you care about. `pmset -g custom` shows power settings, `sysctl iogpu.wired_limit_mb` shows the current GPU limit if supported, and `defaults read` can inspect each preference in the script. If the launch daemon already exists, preserve its contents and metadata: the script overwrites that path.

### Remove the boot daemon

These commands target the daemon installed by this project. If the file existed beforehand, restore your original copy instead of assuming it can be discarded.

```bash
sudo launchctl bootout system /Library/LaunchDaemons/com.custom.unleash.plist
```

If launchd says the service is not loaded, confirm with `sudo launchctl print system/com.custom.unleash`. Resolve other errors before proceeding. After unloading, remove the project's plist:

```bash
sudo rm /Library/LaunchDaemons/com.custom.unleash.plist
```

This prevents the boot task from applying settings again. It does not undo settings already applied during this boot.

### Restore wireless interfaces

Remove the boot daemon first, then bring back each interface that exists:

```bash
sudo ifconfig awdl0 up
sudo ifconfig llw0 up
```

Test the affected feature again. macOS manages these interfaces dynamically, so their state can change afterward.

### Restore Bonjour advertising

If `NoMulticastAdvertisements` was absent before installation, remove the added override:

```bash
sudo defaults delete /Library/Preferences/com.apple.mDNSResponder.plist NoMulticastAdvertisements
sudo killall -HUP mDNSResponder
```

If it had a previous value, restore that value instead. A message saying the key does not exist means there is no such override to delete. Test discovery with the actual application or device afterward.

### Restore the GPU wired memory limit

Remove the boot daemon first. If you recorded a previous limit and the key is supported, restore it with `sudo sysctl -w iogpu.wired_limit_mb=VALUE`, replacing `VALUE` with the number you recorded. Do not guess a memory limit.

If no previous value is available, reboot after removing the daemon so the project's setting is no longer reapplied. Check the limit afterward; other software or system configuration may also affect it.

### Restore interface and keyboard preferences

Restore recorded values for the keys and domains listed in `unleash-mac.sh`. For keys originally absent, `defaults delete DOMAIN KEY` removes the override. Deleting an override does not recover an overwritten custom value.

For example, if the Dock delay key was originally absent:

```bash
defaults delete com.apple.dock autohide-delay
killall Dock
```

Apply the same reasoning to Finder and global preferences. Applications may need to restart, or you may need to sign out for changes to take effect.

### Restore service overrides and power settings

If the analytics and diagnostic services were enabled before this script, remove its disabling overrides with:

```bash
sudo launchctl enable system/com.apple.analyticsd
sudo launchctl enable system/com.apple.diagnosticd
```

These commands do not guarantee the services start immediately. Check their state on your macOS version. Preserve any disabling policy that existed before this project.

Restore power settings from your recorded `pmset -g custom` output or your preferred System Settings configuration. There is no universal set of previous values this guide can recover.

### Remove installed software

Use Homebrew to uninstall only packages and applications you know this run added and no longer need. The script does not record which ones were already installed. Avoid bulk cleanup that could remove unrelated software. Claude Code, when installed through npm, is separate from the Brewfile collection.

If this run installed Homebrew, it may also have added `eval "$(/opt/homebrew/bin/brew shellenv)"` to `~/.zprofile`. Keep that line while you use Homebrew. If you later uninstall Homebrew, review your shell configuration and remove only the initialization you no longer need.
