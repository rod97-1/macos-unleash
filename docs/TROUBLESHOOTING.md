# Troubleshooting

Start with the exact command and error, then run `python3 unleash.py doctor`. Diagnostics report OS family, architecture, Python version, and prerequisite availability without requesting a full hardware report. Remove personal information and credentials before posting output in [an issue](https://github.com/rod97-1/macos-unleash/issues).

## Common problems

| Symptom | What to check |
| --- | --- |
| Python version error | Install Python 3.10 or newer. See the platform guide; do not install project dependencies with pip because none are required. |
| Unsupported OS | Ubuntu, Debian, Fedora, and native Apple Silicon macOS are supported targets. Windows and other Linux distribution IDs are rejected before changes. |
| Missing package prerequisites | Install the native package manager tools and use working official repositories. `doctor` lists the missing commands. |
| Package unavailable | Resolve the native repository error or tool mapping. No unsigned packages, TLS bypass, or guessed repositories are needed. Fedora virtual providers are resolved by DNF. |
| Manual prerequisite | The selected tool has no automatic installer for this platform. Follow its official instructions, or use `--exclude TOOL`. Plan shows the guidance. |
| APT or DNF permission error | Use your normal account with sudo access. The launcher elevates system package commands only. |
| Homebrew refuses root | Run as your normal user. Do not use `sudo python3` or `sudo brew`. |
| Executable exists but status says missing | A mapped tool is checked through its native package records, not merely PATH. This avoids treating a different installation as the requested package. |
| AI tool passes status but cannot serve a model | Status checks installation/command availability. Models, server startup, authentication, and inference health are separate. |
| GNOME desktop session missing | Run desktop tuning from your normal logged-in GNOME session. Headless containers and KDE are not modified. |
| Performance power profile unavailable | The hardware/service does not advertise it. The launcher will not invent a replacement. |
| Mac legacy daemon detected | Follow [migration](MACOS.md#migrating-an-existing-boot-daemon) before selecting tuning. Package-only workflows remain available. |
| Mac preferences appear unchanged | Written values were checked, but the application or OS may need a restart/sign-out or may not honor that preference on this release. |
| Restore conflict | A recorded value changed outside the launcher. Inspect the affected setting and decide which value to keep. Restore will not overwrite that decision automatically. |
| Journal permission or ownership error | Use the same account and private state directory as apply. Do not broadly chmod a shared directory to make the check pass. |
| Another operation holds the recovery lock | Wait for the existing apply/restore operation to finish. Do not delete its lock file to run concurrently. |

## Partial failures and retries

Package installation is not a transaction: a native package manager may successfully install some tools before a later error. The launcher stops and returns a failing exit status. Already installed packages remain installed.

Retry the same selection after fixing the actual error:

```bash
python3 unleash.py plan --profile core --profile dev
python3 unleash.py apply --profile core --profile dev
python3 unleash.py status --profile core --profile dev
```

Already satisfied tools are skipped. Settings are applied only after selected tool prerequisites and installation have succeeded. An unsupported tuning request fails before package installation.

A setting failure can leave earlier selected settings applied. Original values are written to the recovery journal before each setting write, including a failed attempt. Retry after resolving the error or use recovery. Do not delete the journal to dismiss a failure.

## Recovery

```bash
python3 unleash.py restore
python3 unleash.py restore --run RUN_ID
```

Use the same `--state-dir` if it was overridden during apply. Default paths are documented in the README. State belongs to the same user, OS family, and architecture; restore also assumes it is on the same machine. Do not transfer journals to another machine. The launcher deliberately avoids recording machine serial numbers or hostnames.

The original setting baseline is retained across repeated apply runs. If a later run changed a managed value, restore that later run first. Recovery stops on current-value conflicts and validates all selected records before starting writes. If restoration itself fails after some successful writes, completed records are removed and remaining records are retained for retry.

Recovery does not uninstall packages, downgrade dependencies, remove models, undo authentication, or reverse changes that were never recorded. Keep backups for broader workstation recovery.

## Legacy Mac recovery

The old Bash-only script did not record originals. The Python recovery journal cannot recover those missing values. First unload and remove the confirmed project daemon using [the migration guide](MACOS.md#migrating-an-existing-boot-daemon). Do not delete an unrelated pre-existing daemon at the same path.

After unloading, restore existing wireless interfaces if needed:

```bash
sudo ifconfig awdl0 up
sudo ifconfig llw0 up
```

For the GPU limit, use a previously recorded value if you have one. Otherwise reboot after removing the daemon so its setting is no longer reapplied, then inspect `sysctl iogpu.wired_limit_mb`. Other system configuration may also affect it.

If `NoMulticastAdvertisements` was originally absent, remove that old override and reload the service:

```bash
sudo defaults delete /Library/Preferences/com.apple.mDNSResponder.plist NoMulticastAdvertisements
sudo killall -HUP mDNSResponder
```

If the key had an original custom value, restore it instead. For previously enabled analytics/diagnostic services, `sudo launchctl enable system/com.apple.analyticsd` and the equivalent `diagnosticd` command restore an enabled override. They do not guarantee immediate startup. Preserve policies that existed before this project.

Restore other preferences and power values from your own records or backup. Removing a defaults override cannot reconstruct an overwritten custom value. Uninstall only applications you know the old script added and no longer need; it did not record pre-existing software.
