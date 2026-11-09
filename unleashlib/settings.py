"""Capability-checked, opt-in workstation settings. No boot daemon is created."""

from dataclasses import dataclass
import math
import os
from pathlib import Path
import plistlib
import re
from typing import Callable

LEGACY_DAEMON = Path("/Library/LaunchDaemons/com.custom.unleash.plist")
GROUPS = ("desktop", "power", "services", "wireless")


class SettingsError(RuntimeError):
    pass


def _scalar(value):
    if value is not None and (
        type(value) not in (bool, int, float, str)
        or (type(value) is float and not math.isfinite(value))
    ):
        raise SettingsError("Invalid scalar setting snapshot.")


def _boolean(value):
    if type(value) is not bool:
        raise SettingsError("Setting snapshot must be boolean.")


def _integer(value, maximum=2**31 - 1):
    if type(value) is not int or not 0 <= value <= maximum:
        raise SettingsError(
            "Setting snapshot must be an integer within supported bounds."
        )


def _profile(value):
    if type(value) is not str or value not in (
        "balanced",
        "performance",
        "power-saver",
    ):
        raise SettingsError("Invalid power profile snapshot.")


@dataclass
class Setting:
    id: str
    label: str
    read: Callable
    write: Callable
    desired: object
    validate: Callable = _scalar

    def __post_init__(self):
        writer = self.write

        def checked_write(value):
            self.validate(value)
            return writer(value)

        self.write = checked_write


def _require(runner, *commands):
    missing = [name for name in commands if not runner.which(name)]
    if missing:
        raise SettingsError("Missing setting capability: " + ", ".join(missing))


def _privileged(runner, argv):
    if os.geteuid() == 0:
        return argv
    _require(runner, "sudo")
    return ["sudo", *argv]


def _preference(runner, setting_id, domain, key, desired, system=False):
    def command(args):
        return _privileged(runner, args) if system else args

    def read():
        result = runner.run(["defaults", "export", domain, "-"], check=False)
        if result.returncode:
            error = (result.stderr + result.stdout).lower()
            if "does not exist" in error or "not found" in error:
                return None
            raise SettingsError(
                f"Cannot read preference domain {domain}: {result.stderr.strip()}"
            )
        try:
            value = plistlib.loads(result.stdout.encode()).get(key)
        except (ValueError, plistlib.InvalidFileException, AttributeError) as exc:
            raise SettingsError(f"Invalid preference data for {domain}") from exc
        if value is not None and (
            type(value) not in (bool, int, float, str)
            or (isinstance(value, float) and not math.isfinite(value))
        ):
            raise SettingsError(f"Unsupported original preference type: {domain}/{key}")
        return value

    def write(value):
        args = ["defaults", "delete", domain, key]
        if value is not None:
            flag = {bool: "-bool", int: "-int", float: "-float", str: "-string"}[
                type(value)
            ]
            rendered = str(value).lower() if isinstance(value, bool) else str(value)
            args = ["defaults", "write", domain, key, flag, rendered]
        runner.run(command(args))

    return Setting(setting_id, f"{domain}: {key}", read, write, desired)


def _linux(runner, groups):
    settings = []
    if "services" in groups or "wireless" in groups:
        raise SettingsError(
            "services and wireless tuning are macOS-only; Linux does not copy these changes."
        )
    if "desktop" in groups:
        if not os.environ.get("DBUS_SESSION_BUS_ADDRESS"):
            raise SettingsError(
                "GNOME tuning requires your active desktop session; no session was detected."
            )
        _require(runner, "gsettings")
        key = ["org.gnome.desktop.interface", "enable-animations"]
        result = runner.run(["gsettings", "writable", *key])
        if result.stdout.strip() != "true":
            raise SettingsError("GNOME animation setting is unavailable or locked.")

        def read_animation():
            text = runner.run(["gsettings", "get", *key]).stdout.strip()
            if text not in ("true", "false"):
                raise SettingsError("Cannot read GNOME animation value.")
            return text == "true"

        def write_animation(value):
            if type(value) is not bool:
                raise SettingsError("GNOME animation state must be boolean.")
            runner.run(["gsettings", "set", *key, str(value).lower()])

        settings.append(
            Setting(
                "linux.desktop.animations",
                "GNOME animations",
                read_animation,
                write_animation,
                False,
                _boolean,
            )
        )
    if "power" in groups:
        _require(runner, "powerprofilesctl")
        output = runner.run(["powerprofilesctl", "list"]).stdout
        if not re.search(r"\bperformance\s*:", output):
            raise SettingsError(
                "This machine does not expose a performance power profile."
            )

        def read_power():
            value = runner.run(["powerprofilesctl", "get"]).stdout.strip()
            if value not in ("balanced", "performance", "power-saver"):
                raise SettingsError("Unrecognized power profile.")
            return value

        def write_power(value):
            if value not in ("balanced", "performance", "power-saver"):
                raise SettingsError("Invalid power profile snapshot.")
            runner.run(["powerprofilesctl", "set", value])

        settings.append(
            Setting(
                "linux.power.profile",
                "System power profile",
                read_power,
                write_power,
                "performance",
                _profile,
            )
        )
    return settings


def _mac(runner, groups, gpu_limit_mb):
    settings = []
    if LEGACY_DAEMON.exists():
        raise SettingsError(
            "Remove or migrate the legacy com.custom.unleash boot daemon before tuning. See docs/MACOS.md."
        )
    if "desktop" in groups:
        _require(runner, "defaults")
        preferences = [
            ("dock.magnification", "com.apple.dock", "magnification", False),
            ("dock.autohide-time", "com.apple.dock", "autohide-time-modifier", 0.0),
            ("dock.autohide-delay", "com.apple.dock", "autohide-delay", 0.0),
            ("dock.launchanim", "com.apple.dock", "launchanim", False),
            ("finder.animations", "com.apple.finder", "DisableAllAnimations", True),
            (
                "global.animations",
                "NSGlobalDomain",
                "NSAutomaticWindowAnimationsEnabled",
                False,
            ),
            ("global.resize", "NSGlobalDomain", "NSWindowResizeTime", 0.001),
            ("global.appnap", "NSGlobalDomain", "NSAppSleepDisabled", True),
            ("global.keyrepeat", "NSGlobalDomain", "KeyRepeat", 1),
            ("global.initialrepeat", "NSGlobalDomain", "InitialKeyRepeat", 10),
        ]
        settings.extend(
            _preference(runner, "mac." + sid, domain, key, value)
            for sid, domain, key, value in preferences
        )
    if "power" in groups:
        _require(runner, "pmset")

        def read_power_key(key):
            text = runner.run(["pmset", "-g", "custom"]).stdout
            match = re.search(r"AC Power:\s*\n(.*?)(?=\n\S|\Z)", text, re.S)
            value = (
                re.search(
                    r"^\s*" + re.escape(key) + r"\s+(\d+)\s*$", match.group(1), re.M
                )
                if match
                else None
            )
            if not value:
                raise SettingsError(f"Unsupported charger power setting: {key}")
            return int(value.group(1))

        for key, desired in [("sleep", 0), ("displaysleep", 20)]:
            settings.append(
                Setting(
                    "mac.power." + key,
                    "Charger " + key,
                    lambda key=key: read_power_key(key),
                    lambda value, key=key: runner.run(
                        _privileged(runner, ["pmset", "-c", key, str(value)])
                    ),
                    desired,
                    _integer,
                )
            )
    if "services" in groups:
        _require(runner, "launchctl", "defaults")
        for service in ("com.apple.analyticsd", "com.apple.diagnosticd"):

            def read_service(service=service):
                output = runner.run(["launchctl", "print-disabled", "system"]).stdout
                value = re.search(
                    r'"' + re.escape(service) + r'"\s*=>\s*(true|false)', output
                )
                if value:
                    return value.group(1) == "true"
                if runner.run(
                    ["launchctl", "print", "system/" + service], check=False
                ).returncode:
                    raise SettingsError(f"Service unavailable: {service}")
                return False

            settings.append(
                Setting(
                    "mac.service." + service.rsplit(".", 1)[1],
                    "Disable " + service,
                    read_service,
                    lambda value, service=service: runner.run(
                        _privileged(
                            runner,
                            [
                                "launchctl",
                                "disable" if value else "enable",
                                "system/" + service,
                            ],
                        )
                    ),
                    True,
                    _boolean,
                )
            )
        settings.append(
            _preference(
                runner,
                "mac.bonjour.advertising",
                "/Library/Preferences/com.apple.mDNSResponder.plist",
                "NoMulticastAdvertisements",
                True,
                system=True,
            )
        )
    if "wireless" in groups:
        _require(runner, "ifconfig")
        for interface in ("awdl0", "llw0"):

            def read_interface(interface=interface):
                result = runner.run(["ifconfig", interface], check=False)
                flags = re.search(r"flags=[0-9a-fA-F]+<([^>]+)>", result.stdout)
                if result.returncode or not flags:
                    raise SettingsError(f"Wireless interface unavailable: {interface}")
                return "UP" in flags.group(1).split(",")

            settings.append(
                Setting(
                    "mac.wireless." + interface,
                    interface + " (affects AirDrop)",
                    read_interface,
                    lambda value, interface=interface: runner.run(
                        _privileged(
                            runner, ["ifconfig", interface, "up" if value else "down"]
                        )
                    ),
                    False,
                    _boolean,
                )
            )
    if gpu_limit_mb is not None:
        _require(runner, "sysctl")
        try:
            total_mb = (
                int(runner.run(["sysctl", "-n", "hw.memsize"]).stdout.strip())
                // 1024**2
            )
        except ValueError as exc:
            raise SettingsError(
                "Cannot determine physical memory for GPU limit validation."
            ) from exc
        maximum = min(total_mb * 80 // 100, total_mb - 4096)
        if not 0 < gpu_limit_mb <= maximum:
            raise SettingsError(
                f"GPU limit must be between 1 and {maximum} MiB; keep at least 4 GiB and 20 percent for other uses."
            )

        def read_gpu():
            try:
                return int(
                    runner.run(["sysctl", "-n", "iogpu.wired_limit_mb"]).stdout.strip()
                )
            except ValueError as exc:
                raise SettingsError("Unsupported GPU wired memory limit.") from exc

        settings.append(
            Setting(
                "mac.gpu.limit",
                "GPU wired memory limit (MiB)",
                read_gpu,
                lambda value: runner.run(
                    _privileged(
                        runner, ["sysctl", "-w", f"iogpu.wired_limit_mb={value}"]
                    )
                ),
                gpu_limit_mb,
                lambda value: _integer(value, total_mb),
            )
        )
    return settings


def build_settings(platform, runner, groups, gpu_limit_mb):
    if any(group not in GROUPS for group in groups):
        raise SettingsError("Unknown tuning group.")
    if not groups and gpu_limit_mb is None:
        return []
    if os.geteuid() == 0:
        raise SettingsError(
            "Run tuning as your normal user, not root; individual system changes request sudo when needed."
        )
    if platform.name != "macos" and gpu_limit_mb is not None:
        raise SettingsError("GPU wired memory limits are macOS-only.")
    settings = (
        _mac(runner, groups, gpu_limit_mb)
        if platform.name == "macos"
        else _linux(runner, groups)
    )
    for setting in settings:
        setting.read()  # Validate the complete requested set before any mutation.
    return settings


def group_for_id(setting_id):
    if setting_id == "mac.gpu.limit":
        return "gpu"
    if setting_id.startswith(
        ("mac.dock.", "mac.finder.", "mac.global.", "linux.desktop.")
    ):
        return "desktop"
    if setting_id.startswith(("mac.power.", "linux.power.")):
        return "power"
    if setting_id.startswith(("mac.service.", "mac.bonjour.")):
        return "services"
    if setting_id.startswith("mac.wireless."):
        return "wireless"
    raise SettingsError(f"Unknown setting identifier: {setting_id}")
