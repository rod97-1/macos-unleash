"""A small common interface around native package managers and settings."""

import argparse
import os
from pathlib import Path
import shlex
import sys
from .catalog import CatalogError, PROFILES, load_catalog, select_tools
from .packages import PackageError, PackageManager
from .platforms import PlatformError, detect_platform
from .runner import CommandError, Runner
from .settings import GROUPS, LEGACY_DAEMON, SettingsError, build_settings, group_for_id
from .state import StateError, StateStore


def parser():
    root = argparse.ArgumentParser(
        description="Workstation setup for Ubuntu, Debian, Fedora, and Apple Silicon macOS. Windows is deferred."
    )
    sub = root.add_subparsers(dest="command")
    sub.add_parser("doctor", help="inspect platform and prerequisites without changes")
    for name, help_text in [
        ("plan", "preview selected actions without changes"),
        ("apply", "install selected tools and apply explicit tuning"),
        ("status", "check selected tools and settings"),
    ]:
        command = sub.add_parser(name, help=help_text)
        command.add_argument(
            "--profile",
            action="append",
            choices=PROFILES,
            default=[],
            help="repeat to combine profiles; defaults to core when no tools are selected",
        )
        command.add_argument(
            "--tool",
            action="append",
            default=[],
            help="select an individual tool ID; repeat for more tools",
        )
        command.add_argument(
            "--exclude", action="append", default=[], help="exclude a tool ID"
        )
        command.add_argument(
            "--no-packages",
            action="store_true",
            help="select only tuning, without any package profile",
        )
        command.add_argument(
            "--tune",
            action="append",
            choices=GROUPS,
            default=[],
            help="explicit system setting group; none by default",
        )
        command.add_argument(
            "--gpu-limit-mb",
            type=int,
            help="explicit macOS GPU wired limit in MiB; no default",
        )
        command.add_argument(
            "--state-dir", type=Path, help="private recovery directory"
        )
    restore = sub.add_parser(
        "restore", help="restore recorded settings; never uninstall packages"
    )
    restore.add_argument("--run", help="run ID; defaults to latest recorded run")
    restore.add_argument(
        "--state-dir", type=Path, help="private recovery directory used during apply"
    )
    return root


def state_path(platform):
    if platform.name == "macos":
        return Path.home() / "Library" / "Application Support" / "macos-unleash"
    return (
        Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local" / "state")))
        / "macos-unleash"
    )


def restore_handlers(platform, runner, data, run_id):
    if not data["runs"]:
        raise StateError("No recovery runs found.")
    run_id = run_id or sorted(data["runs"])[-1]
    if run_id not in data["runs"]:
        raise StateError("Unknown recovery run.")
    groups = set()
    gpu = None
    for sid in data["runs"][run_id]:
        entry = data["settings"].get(sid)
        if entry is None:
            continue
        group = group_for_id(sid)
        if group == "gpu":
            if type(entry["after"]) is not int:
                raise StateError("Invalid GPU recovery snapshot.")
            gpu = entry["after"]
        else:
            groups.add(group)
    return {s.id: s for s in build_settings(platform, runner, sorted(groups), gpu)}


def main(argv=None):
    root = parser()
    args = root.parse_args(argv)
    if args.command is None:
        root.print_help()
        return 0
    try:
        platform = detect_platform()
        runner = Runner()
        manager = PackageManager(platform, runner)
        if args.command == "doctor":
            print(
                f"Platform: {platform.name} ({platform.arch})\nPython: {sys.version.split()[0]}\nPackage manager: {platform.manager}"
            )
            missing = []
            for name in manager.required_commands:
                found = bool(runner.which(name))
                print(f"{name}: {'available' if found else 'missing'}")
                if not found:
                    missing.append(name)
            if platform.name == "macos" and LEGACY_DAEMON.exists():
                print(
                    "Legacy boot daemon detected: migrate before selecting tuning. See docs/MACOS.md."
                )
            print(
                "This checks prerequisites only; use status to inspect selected tools. Desktop tuning needs an active supported session."
            )
            return 1 if missing else 0
        store = StateStore(args.state_dir or state_path(platform), platform)
        if args.command == "restore":
            data = store.load()
            handlers = restore_handlers(platform, runner, data, args.run)
            count = store.restore(handlers, args.run)
            print(
                f"Restored {count} recorded setting(s). Installed packages were not removed."
            )
            return 0
        if args.no_packages and (args.profile or args.tool or args.exclude):
            raise CatalogError(
                "--no-packages cannot be combined with package selectors."
            )
        catalog = load_catalog()
        tools = (
            []
            if args.no_packages
            else select_tools(catalog, args.profile, args.tool, args.exclude)
        )
        missing_commands = (
            [name for name in manager.required_commands if not runner.which(name)]
            if tools
            else []
        )
        if missing_commands:
            raise PackageError(
                "Missing prerequisites: "
                + ", ".join(missing_commands)
                + ". Run doctor and install the native package manager first."
            )
        settings = build_settings(platform, runner, args.tune, args.gpu_limit_mb)
        print(f"Platform: {platform.name} ({platform.arch})")
        missing = []
        manual = []
        for tool in tools:
            installed = manager.installed(tool)
            mapped = bool(manager.packages(tool))
            status = (
                "installed"
                if installed
                else "missing"
                if mapped
                else "manual prerequisite"
            )
            print(f"{tool.id}: {status}")
            if not installed:
                missing.append(tool)
                if not mapped:
                    manual.append(tool)
                    print("  " + tool.guidance)
        different = []
        for setting in settings:
            current = setting.read()
            print(f"{setting.id}: {current!r} -> {setting.desired!r}")
            if current != setting.desired:
                different.append(setting)
        if args.command == "status":
            return 1 if missing or different else 0
        if args.command == "plan":
            for command in manager.commands(
                [t for t in missing if manager.packages(t)]
            ):
                print("Would run: " + shlex.join(command))
            print(f"Settings to change: {len(different)}. No changes made.")
            if manual:
                print(
                    "Apply is blocked until the listed manual prerequisites are available or excluded."
                )
            return 0
        if manual:
            raise PackageError(
                "Resolve or exclude manual prerequisites before apply. No packages or settings were changed."
            )
        # Validate journal context and conflicts before installing any packages.
        if settings:
            store.check(settings)
        installed = manager.install(tools)
        print(
            f"Installed and verified {len(installed)} tool(s); {len(tools) - len(installed)} already present."
        )
        if settings:
            run_id = store.apply(settings)
            if run_id:
                print(f"Settings applied and verified. Recovery run: {run_id}")
            else:
                print(
                    "Selected settings already match. Existing original snapshots were retained."
                )
            if platform.name == "macos":
                print(
                    "Some macOS preferences need an application restart or sign-out. No applications were terminated."
                )
        else:
            print("No system tuning selected.")
        return 0
    except (
        PlatformError,
        CatalogError,
        PackageError,
        SettingsError,
        StateError,
        CommandError,
        OSError,
    ) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        if args.command in ("apply", "restore"):
            print(
                "Stopped. Any earlier successful actions may remain. Retry after resolving the error; use restore for recorded settings.",
                file=sys.stderr,
            )
        return exc.code if isinstance(exc, CommandError) else 2
    except KeyboardInterrupt:
        print(
            "Interrupted. Earlier actions may remain; recovery snapshots are retained.",
            file=sys.stderr,
        )
        return 130
