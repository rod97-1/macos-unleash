# Project audit

Review date: November 9, 2026.

Scope: the current Bash script, Brewfile, README, and public repository description. This is a static correctness and maintainability review. The review environment is Linux x86_64; macOS behavior and performance were not tested.

## Summary

The main release gaps are platform checks, reliable failure reporting, backups, and repeatable validation. Documentation now describes these limits. The script has not been changed as part of this documentation review.

The current tracked files contain no personal machine serial number, hostname, account path, or fixed personal hardware configuration. The public About description names chip models and a fixed GPU memory amount. Replace it with:

> Apple Silicon macOS workstation bootstrap for desktop preferences, power settings, wireless interfaces, GPU memory limits, and Homebrew software installation.

The public description is repository metadata, separate from the README. Changing files does not change that field. Historical commits were not rewritten or assessed for personal information.

## Findings

| Priority | Finding and source | Effect | Recommended change |
| --- | --- | --- | --- |
| High | No platform or prerequisite validation. Hardware detection pipelines use `awk` without `pipefail`; `unleash-mac.sh:4–5`. | A failed detector can produce empty output without stopping the script. Unsupported machines can reach later stages; invalid memory does not reliably stop execution. | Validate Darwin, native arm64, required commands, model detection, and numeric memory before privileges or mutations. |
| High | No backup or rollback; preference changes start at `unleash-mac.sh:16`. | Previous values are overwritten. Later failure leaves a partially configured machine. A pre-existing daemon at the same path is replaced. | Record previous values and file state, provide a dry run, and restore only changes made by a specific run. |
| High | Daemon commands use semicolons without postcondition checks; `unleash-mac.sh:59`. | Earlier failures can be hidden by the last command. On the lower-memory path the final command is `true`. | Check each command, handle absent interfaces, and report resulting interface and GPU state. |
| High | GPU limit is chosen from total memory alone; `unleash-mac.sh:38–41`. | An OS-specific key is attempted without checking support or workload memory needs. No benchmark supports the selected percentage. | Make this an explicit choice, check support and bounds, and measure results before calling it optimal. |
| Medium | Service errors are suppressed; `unleash-mac.sh:29–32`. | Completion can be reported when requested service changes were rejected. | Report optional failures separately and print a result summary. |
| Medium | Power option support is not checked; `unleash-mac.sh:73–77`. | Unsupported options can stop a run after earlier mutations. The non-Studio branch assumes charger and battery profiles are appropriate. | Check power capabilities and supported options before applying a profile. |
| Medium | No cleanup trap for the sudo refresher; `unleash-mac.sh:13`. | After the parent exits, the helper remains until its next sleep interval completes. Signals and early failures have no explicit cleanup path. | Track its PID and stop it using an EXIT trap. |
| Medium | Tool installation follows system mutation; `unleash-mac.sh:80–94`. | Network or installer failures occur after machine settings have changed. Versions are unpinned and runtime tests are absent. | Validate installation prerequisites early, separate installation from tuning, and test supported Mac configurations. |

## Documentation changes completed

The README explains prerequisites, the workflow, the software collection, verification, and the distinction between a memory limit and allocated memory. A Mermaid diagram shows execution order. The troubleshooting guide covers common failures and the limits of manual recovery.

The introduction no longer promises zero stutter or implies benchmarked kernel optimization. Hardware examples and fixed personal specifications are not needed to explain the project.

## Validation

`bash -n unleash-mac.sh` passes in the Linux review environment. This is syntax validation only. The repository has no existing automated test suite or CI configuration. The documented verification and recovery commands require macOS and have not been executed here.

Before release, test failures and recovery on a suitable Mac, check supported macOS versions and package availability, and have the maintainer choose a license. A successful run should report observed results rather than infer them from launchd or installer exit status alone.
