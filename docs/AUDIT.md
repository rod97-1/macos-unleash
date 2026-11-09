# Project audit

Review date: November 9, 2026. Scope: the Python launcher, platform adapters, tool catalog, recovery state, compatibility wrapper, tests, and documentation.

## Changes from the original bootstrap

| Original issue | Current behavior |
| --- | --- |
| No OS or prerequisite guard | Explicit Ubuntu, Debian, Fedora, and native Apple Silicon detection. Other platforms fail before mutation. |
| Settings applied as soon as the script runs | No-argument help, doctor, plan, and status do not mutate the machine. Settings require explicit apply and tuning selection. |
| Preferences and files overwritten without originals | Selected setting snapshots are written atomically before changes. Journal context, ownership, permissions, and schema are checked. |
| Daemon command failures could be hidden | No new daemon is created. Each setting write is checked, then read back. Existing legacy daemon files block tuning until migration. |
| Automatic GPU limit chosen from RAM size | No automatic GPU tuning. Mac users choose an explicit positive limit subject to capability and memory bounds. Linux GPU tuning is not implemented. |
| Silent service failures | Failures stop execution with a nonzero status. Earlier actions are explicitly reported as potentially remaining. |
| Broad power changes on unvalidated hardware | Linux requires an advertised performance profile. Mac changes only supported charger sleep/display settings and preserves battery settings. |
| Detached privileged keepalive | Removed. The launcher runs as a normal user, elevating native system commands when needed. |
| Remote installer execution and shell-profile rewriting | Removed from the launcher. Python and package managers are prerequisites. External optional tools have manual instructions. |
| No test suite | Standard-library unit tests, disposable native Linux package integration, and Linux/macOS CI configuration are included. |

The original Mac tool collection remains in Brewfile. A parity test checks its 31 entries against the full Mac catalog. Default core/dev profiles are smaller, and unsupported optional software is reported explicitly.

## Validation evidence

| Check | Observed result |
| --- | --- |
| Unit suite | 63 tests pass for platform, catalog, native command construction, failures, capability fixtures, CLI boundaries, and recovery behavior. |
| Ubuntu 24.04 x86_64 container | Core/dev package installation, status verification, repeat apply with zero new installations, and mutation-free plan passed. |
| Debian 13 x86_64 container | Same native package checks passed. |
| Fedora 44 x86_64 container | Same checks passed after fixing virtual-provider handling for package names such as wget. |
| Cloud Debian host | Read-only doctor and plan work. Status accurately reports native selected packages that are missing. No system tuning was applied. |
| Mac and Linux desktop adapters | Exercised with command fixtures and temporary recovery state. No claim of native desktop, power, or GPU validation. |

The container bootstrap preserves repository signatures and TLS verification, using the cloud CA bundle where required. Package installations were confined to disposable containers. These results do not measure workstation performance.

Independent review identified two recovery defects before publication: a failed re-apply could lose the preceding managed value, and generic journal scalars could reach setting writers without type checks. Regression tests reproduced both. The journal now records pending writes and their preceding values; handler-specific validation runs before any restore write, with validation also enforced by the writers. The full suite passed after both corrections.

## Remaining limits

Native macOS changes and physical Linux desktop/power behavior still need testing on suitable machines. Linux arm64 detection is present, but package integration was exercised on x86_64. Windows is explicitly deferred. Supported package availability and current distribution versions remain prerequisites.

Recovery is scoped to recorded setting values. It does not roll back package-manager transactions, models, authentication, or changes from the original Bash-only bootstrap. System settings can change outside the launcher; recovery stops on conflicts. Journals must remain on the same machine and user account, even though identifying hardware data is deliberately not stored. Recovery preserves a managed baseline, not a full workstation snapshot.

Launchd service recovery restores the recorded enabled/disabled state; it does not erase every historical override entry. macOS may ignore a written preference on some releases even if the stored value verifies. No benchmarks establish reduced stutter or improved inference performance.

Optional tools outside signed distro packages require separate installation. Linux full-profile parity with Mac-only applications is neither implemented nor implied. An executable check does not establish application authentication, model readiness, or service health.

The public About description is generic. Project files contain no fixed personal workstation configuration; historical commits were not rewritten or audited for personal data. The maintainer still needs to choose a license before a licensed release.
