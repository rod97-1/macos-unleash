# Workstation launcher design

Status: proposed for review.

## Intent

Improve the reliability and organization of the existing workstation bootstrap, then extend its development and local AI setup workflow to Ubuntu, Debian, and Fedora. Use one Python launcher across platforms. Implement Windows only after the Linux version is working and validated.

Keep the current repository name and the visual style of its README. Platform support must be described precisely, without personal computer specifications or unsupported performance promises.

## Decisions from the discussion

The maintainer chose a Python launcher over separate native implementations. The first Linux targets are Ubuntu, Debian, and Fedora. Windows is a later phase, not a supported platform in this delivery.

Two approaches were considered. Native Bash and PowerShell scripts avoid a Python prerequisite but duplicate argument parsing, planning, logging, and recovery logic. A Python launcher adds a runtime prerequisite but provides one command interface and a common implementation of those behaviors. The selected approach is Python with small platform adapters.

The following are implementation proposals, not additional maintainer decisions.

## Scope of this delivery

Provide a Python 3.10 or newer command line application using only the standard library at runtime. Keep dependencies out of the installation path for the launcher itself. Separate platform detection, package catalogs, command execution, state storage, and tuning into modules.

Support Ubuntu and Debian through APT, Fedora through DNF, and the existing Apple Silicon Mac workflow through Homebrew. Detect distribution identity from os-release data; reject unsupported systems before privileges or mutations. Report required tools, Python version, architecture, and package manager availability in a diagnostic command without exposing identifying hardware information.

The legacy `unleash-mac.sh` becomes a small compatibility entry point for the Python launcher. Keep `Brewfile` usable independently and ensure its relationship to the Mac catalog is tested. Python and package managers are prerequisites; do not silently run downloaded installation scripts to acquire them.

Do not add a working Windows adapter in this phase. On Windows the launcher should give a clear unsupported-platform message and perform no changes.

## Command interface

The public entry point is `python3 unleash.py`.

| Command | Behavior |
| --- | --- |
| `doctor` | Inspect platform and prerequisites. Report missing capabilities without changing the machine. |
| `plan` | Show exact intended actions, package manager commands, unsupported tools, and privilege requirements. No installation or system changes. |
| `apply` | Apply an explicitly selected plan. Request elevation only for operations that need it. Report applied, skipped, and failed actions accurately. |
| `status` | Inspect installed tools and supported selected settings. Return a failing status when required selected components are missing. |
| `restore` | Restore recorded setting changes from a selected run. Explain which changes, including package installations, are outside recovery. |

Running without a subcommand shows help and changes nothing. `plan` is the documented first step. Explicit `apply` authorizes the selected operations; do not add repetitive confirmation prompts.

Profiles are `core`, `dev`, `desktop`, and `ai`. A user may select more than one. Default to `core`; document exactly which tools each profile selects. Allow individual tool selection and exclusion. A compatibility or full-collection option can select the old Mac software collection without making every browser and editor a default.

## Tool catalogs

Use data files to map logical tools to platform package identifiers, executable checks, profile membership, and supported installation sources. Handle names such as `node` versus `nodejs` explicitly. Check the selected package identifiers before mutation and distinguish an already installed package from an unsupported mapping.

Preserve the intent of the existing collection: command line utilities, development runtimes, optional desktop applications, and local AI tooling. Do not invent Linux equivalents for Mac-only applications. Clearly mark unsupported entries and suggest an appropriate documented alternative where one exists.

Prefer signed distribution packages and Homebrew packages. Tools absent from official repositories need an explicit supported installation handler or a clear manual prerequisite. Do not silently add third-party repositories, execute downloaded shell scripts, or install unverified binary artifacts. Any binary handler must use an official source and verified published digest with explicit version and architecture selection.

Initially prioritize a complete, verifiable core and development workflow on all three Linux distributions. Optional desktop and AI tools must report their actual support and checks rather than imply that every Mac application is available everywhere.

## System tuning

Package installation and tuning are separate selections. No tuning is implied merely by installing a profile.

On Linux, begin with supported desktop animation and power-profile controls, applying them only when explicitly requested and when the desktop schema or power capability exists. Do not modify boot parameters, GPU memory allocation, wireless interfaces, security controls, or diagnostic services as a generic Linux optimization.

On macOS, make existing preference, power, service, wireless, and GPU changes explicit selections. Check commands and capabilities first. GPU tuning needs an explicit bounded value and a supported sysctl key; do not automatically use 90 percent of RAM. Wireless isolation must be clearly labeled with its AirDrop implications. Do not preserve the old unconditional privileged boot task as a default.

Run commands with argument arrays rather than a shell. Display useful errors and preserve their exit status. Do not suppress failures and later announce complete success. Eliminate the detached sudo refresher; do not run the entire launcher as root when user-session settings need the invoking user's context.

## State and recovery

Before changing a setting, record its exact original value, whether it existed, and the applicable platform and user context. Store state atomically in a user-owned directory using restrictive permissions. Use run identifiers and a versioned data format. Do not record tokens, environment dumps, serial numbers, or full hardware reports.

Recovery reads validated data, not executable state files. It restores only changes recorded for the selected run and reports conflicts when the current value was independently changed afterward. Repeated application must preserve the original baseline for settings already managed rather than overwrite it with the configured value.

State explicitly that package removal, dependency downgrades, downloaded models, application authentication, and unrelated user changes are not covered by setting recovery. Do not uninstall pre-existing tools.

## Validation

Use standard-library unit tests for platform detection, argument handling, catalog selection, safe command construction, and recovery state. Use injected command runners to exercise failure paths without modifying the host. Tests must cover invalid input, unsupported OS, missing commands, unavailable tuning capabilities, partial failure, repeated application, and conflicting recovery.

Run real read-only `doctor`, `plan`, and `status` operations in the current Debian environment. Validate actual package resolution and a representative core installation in disposable Ubuntu, Debian, and Fedora environments where the available runtime supports them. Keep those effects out of the cloud host.

Add CI checks on Linux and macOS for the common launcher, catalog consistency, and read-only commands. Clearly distinguish mocked platform tests from native integration tests. Do not claim that a macOS system change or Linux desktop tuning works merely because a mock passed. Windows support and Windows CI are deferred.

## Documentation and publication

Retain the custom banner, graphic, badges, concise navigation, and expandable reference sections. Update the graphics and wording to show the Linux-first expansion without advertising Windows as ready. Add platform-specific setup, package support, diagnostics, tuning, and recovery instructions. Replace the historical audit's open items with current evidence and remaining limitations as fixes land.

After implementation, review the changes, run the appropriate checks, publish to the repository as previously requested, and verify the published files. Report any native validation that could not run.

## Completion criteria

The launcher has one consistent interface, no mutation occurs from help, doctor, plan, or unsupported-platform paths, and core/development installation is exercised for Ubuntu, Debian, and Fedora. macOS compatibility and the existing software collection are retained with explicit tuning choices. Recorded settings can be recovered under the documented rules. Meaningful automated tests and clear platform documentation ship with the implementation. Windows remains explicitly deferred until the Linux milestone is complete.
