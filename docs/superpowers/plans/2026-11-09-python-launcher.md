# Python launcher implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship one reliable workstation launcher for Ubuntu, Debian, Fedora, and Apple Silicon macOS, with Windows deferred.

**Architecture:** A standard-library Python CLI selects tools from a JSON catalog and delegates to APT, DNF, or Homebrew. Platform settings are separate opt-in operations with typed snapshots and a validated, locked recovery journal. Read-only commands never elevate or create state.

**Tech Stack:** Python 3.10+, unittest, APT, DNF, Homebrew, GitHub Actions, Bash compatibility wrapper.

**Spec:** `docs/superpowers/specs/2026-11-09-cross-platform-design.md`

## Global constraints

Runtime uses only the Python standard library. Support Ubuntu, Debian, Fedora, and Apple Silicon macOS; reject Windows without changes. Preserve the README's visual style. Do not disable verification, execute remote installers, add package repositories, or apply tuning implicitly. Preserve original settings and unrelated user changes. Publication is already authorized by the discussion and approved design.

## Review focus

Unsupported and malformed platform identity must fail before mutation (Task 1). Tool selections and package names must never become shell code (Tasks 1 and 2). Partial package or setting failures must preserve actionable status and original baselines (Tasks 2 and 3). Conflicting, malformed, or wrong-user recovery journals must never drive arbitrary commands (Task 3). Reruns and paths containing spaces must work without replacing originals or altering user state during planning (Tasks 3 and 4).

## File structure

`unleash.py` is the public entry point. `unleashlib/platforms.py` handles identity; `catalog.py` and `catalog.json` handle selection; `runner.py` and `packages.py` handle commands and package managers; `settings.py` defines supported settings; `state.py` handles recovery; `cli.py` orchestrates them. `tests/` uses unittest and test-only runners. `tests/integration-linux.sh` exercises disposable containers. CI, platform guides, troubleshooting, audit, and existing visual assets complete the release.

### Task 1: Platform and catalog foundation

**Files:** `unleashlib/__init__.py`, `platforms.py`, `catalog.py`, `catalog.json`, `tests/test_platforms.py`, `tests/test_catalog.py`, `.gitignore`.

**Interfaces:** `Platform(name, manager, arch)`; `detect_platform(system=None, machine=None, release=None) -> Platform`; `load_catalog() -> dict[str, Tool]`; `select_tools(catalog, profiles, include, exclude) -> list[Tool]`. `Tool` holds ID, profiles, platform package arrays, cask flag, executable check, and manual-install guidance.

- [ ] Add tests for supported distributions, unsupported derivative IDs, macOS arm64, Windows rejection, malformed identity, profiles, unknown selections, exclusions, malicious identifiers, and Brewfile/catalog parity.
- [ ] Run `python3 -m unittest discover -s tests -v`; observe the missing implementation failures.
- [ ] Implement strict detection and validated catalog selection. Core provides portable CLI utilities; dev adds supported distro runtimes. Optional Mac-only or external tools are represented honestly. A `full` profile reproduces the Brewfile set.
- [ ] Run the full suite and commit the foundation.

### Task 2: Package planning and installation

**Files:** `unleashlib/runner.py`, `packages.py`, `tests/helpers.py`, `tests/test_packages.py`.

**Interfaces:** `Runner.run(argv, check=True, live=False) -> CompletedProcess`; `CommandError` preserves a usable exit code. `PackageManager(platform, runner)` provides `installed(tool)`, `commands(tools)`, and `install(tools)`; all commands are argument arrays.

- [ ] Add failing tests for APT, DNF, formula/cask commands; already installed packages; external tools; elevation boundaries; unavailable package preflight; and installer failures preventing later commands.
- [ ] Observe failures, then implement package inspection and planning without privilege or metadata refresh. Apply refreshes package metadata when needed, validates selected identifiers, and installs only missing packages. No full system upgrades or unsigned package options.
- [ ] Verify real subprocess failure status and argument boundaries using temporary executables, run all tests, and commit.

### Task 3: Explicit settings and recovery

**Files:** `unleashlib/settings.py`, `state.py`, `tests/test_settings.py`, `tests/test_state.py`.

**Interfaces:** `Setting(id, label, read, write, desired)` uses typed JSON-compatible snapshots. `build_settings(platform, runner, groups, gpu_limit_mb) -> list[Setting]`. `StateStore(path, platform)` provides locked `apply(settings)` and `restore(settings_by_id, run_id)` operations and reports a run ID/results.

- [ ] Write failing tests for GNOME animations and available power profiles; typed macOS preferences, power settings, service overrides, wireless flags, bounded GPU values; unsupported capabilities; and legacy daemon migration refusal.
- [ ] Implement explicit settings with capability checks. Mac power changes target supported charger settings; battery behavior stays unchanged. Do not create a persistent daemon. Linux settings require a real user desktop session and never tune the container host implicitly.
- [ ] Write failing tests for original/absent values, pending changes on failure, repeat application, conflicts, per-run recovery, path traversal, wrong platform/user, invalid JSON/schema, symlinks, file modes, and locking.
- [ ] Implement atomic restrictive state files with no executable command data. Recovery derives commands from trusted setting definitions and validates all selected records before mutation. Recover only managed setting values, never installed packages.
- [ ] Run the full suite and commit settings and recovery.

### Task 4: CLI, compatibility, and native Linux verification

**Files:** `unleash.py`, `unleashlib/cli.py`, `unleash-mac.sh`, `tests/test_cli.py`, `tests/integration-linux.sh`, `.github/workflows/checks.yml`.

**Interfaces:** `main(argv=None) -> int` implements help, doctor, plan, apply, status, restore. Shared selectors: repeatable `--profile`, `--tool`, `--exclude`; tuning via repeatable `--tune` and optional `--gpu-limit-mb`; state via `--state-dir`; restore uses `--run` or latest. Entry point checks Python version before importing launcher modules.

- [ ] Add failing CLI tests for mutation-free help/doctor/plan/status, unsupported OS, unknown options, selectors, required-component failures, failure summaries, explicit apply, and wrapper paths containing spaces.
- [ ] Implement orchestration, default core selection, capability diagnostics, nonzero missing-component status, migration guidance, and no-state read-only paths. The wrapper checks Darwin/arm64/Python and delegates without sudo.
- [ ] Add CI for Python versions on Ubuntu/macOS and package integration on Ubuntu 24.04, Debian 13, and Fedora 44. Use trusted official images and preserve signature verification.
- [ ] Run real doctor/plan/status in Debian. Run core and dev package apply/status twice in disposable containers, checking the second run is already configured. Preserve TLS trust/proxy configuration in cloud runs. Report container or native desktop limitations precisely.
- [ ] Run all tests and commit.

### Task 5: Platform documentation, graphics, and final review

**Files:** `README.md`, `docs/LINUX.md`, `docs/MACOS.md`, `docs/TROUBLESHOOTING.md`, `docs/AUDIT.md`, `assets/banner.svg`, `assets/workflow.svg`.

- [ ] Document exact profiles, tool availability, Python/package prerequisites, commands, explicit tuning, restore boundaries, and migration from the old daemon. Mark Windows deferred and optional external installers as manual prerequisites.
- [ ] Retain the custom visual layout while updating the banner/workflow for one launcher and multiple platforms. Update the audit with test evidence and unresolved native validation limits.
- [ ] Run all tests, Python compilation, shell syntax, whitespace checks, catalog parity, documentation links, graphic validation, and desktop/mobile README previews.
- [ ] Obtain one fresh whole-branch review against the approved spec. Fix important findings with reproducing tests; rerun the affected suite.
- [ ] Commit, publish to main, verify remote file hashes and CI results, and report exact support and validation limits.
