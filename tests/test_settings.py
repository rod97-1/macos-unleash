import plistlib
import unittest
from unittest.mock import patch
from unleashlib.platforms import Platform
from unleashlib.settings import SettingsError, build_settings
from helpers import FakeRunner


class SettingsTests(unittest.TestCase):
    def test_no_tuning_means_no_commands(self):
        runner = FakeRunner()
        self.assertEqual(
            build_settings(Platform("debian", "apt", "x86_64"), runner, [], None), []
        )
        self.assertFalse(runner.calls)

    @patch("unleashlib.settings.os.geteuid", return_value=1000)
    @patch.dict("os.environ", {"DBUS_SESSION_BUS_ADDRESS": "test"})
    def test_gnome_animation_snapshot_and_write(self, _):
        runner = FakeRunner(
            {
                (
                    "gsettings",
                    "writable",
                    "org.gnome.desktop.interface",
                    "enable-animations",
                ): (0, "true"),
                (
                    "gsettings",
                    "get",
                    "org.gnome.desktop.interface",
                    "enable-animations",
                ): (0, "true"),
            },
            available={"gsettings"},
        )
        settings = build_settings(
            Platform("debian", "apt", "x86_64"), runner, ["desktop"], None
        )
        self.assertEqual(settings[0].read(), True)
        self.assertEqual(settings[0].desired, False)
        settings[0].write(False)
        self.assertIn(
            [
                "gsettings",
                "set",
                "org.gnome.desktop.interface",
                "enable-animations",
                "false",
            ],
            runner.calls,
        )

    @patch("unleashlib.settings.os.geteuid", return_value=1000)
    def test_headless_desktop_is_rejected(self, _):
        with (
            patch.dict("os.environ", {}, clear=True),
            self.assertRaisesRegex(SettingsError, "desktop session"),
        ):
            build_settings(
                Platform("debian", "apt", "x86_64"),
                FakeRunner(available={"gsettings"}),
                ["desktop"],
                None,
            )

    @patch("unleashlib.settings.os.geteuid", return_value=1000)
    def test_power_requires_performance_capability(self, _):
        runner = FakeRunner(
            {("powerprofilesctl", "list"): (0, "balanced:\npower-saver:")},
            available={"powerprofilesctl"},
        )
        with self.assertRaisesRegex(SettingsError, "performance"):
            build_settings(Platform("fedora", "dnf", "x86_64"), runner, ["power"], None)

    @patch("unleashlib.settings.os.geteuid", return_value=1000)
    def test_linux_does_not_accept_mac_wireless_group(self, _):
        with self.assertRaisesRegex(SettingsError, "macOS"):
            build_settings(
                Platform("debian", "apt", "x86_64"), FakeRunner(), ["wireless"], None
            )

    @patch("unleashlib.settings.os.geteuid", return_value=1000)
    @patch("unleashlib.settings.Path.exists", return_value=False)
    def test_mac_preferences_retain_original_types(self, *_):
        xml = plistlib.dumps({"magnification": True}).decode()
        runner = FakeRunner(
            {
                ("defaults", "export", "com.apple.dock", "-"): (0, xml),
                ("defaults", "export", "com.apple.finder", "-"): (
                    0,
                    plistlib.dumps({}).decode(),
                ),
                ("defaults", "export", "NSGlobalDomain", "-"): (
                    0,
                    plistlib.dumps({}).decode(),
                ),
            },
            available={"defaults"},
        )
        settings = build_settings(
            Platform("macos", "brew", "arm64"), runner, ["desktop"], None
        )
        setting = next(s for s in settings if s.id == "mac.dock.magnification")
        self.assertIs(setting.read(), True)
        setting.write(True)
        self.assertIn(
            ["defaults", "write", "com.apple.dock", "magnification", "-bool", "true"],
            runner.calls,
        )
        setting.write(None)
        self.assertIn(
            ["defaults", "delete", "com.apple.dock", "magnification"], runner.calls
        )

    @patch("unleashlib.settings.os.geteuid", return_value=1000)
    @patch("unleashlib.settings.Path.exists", return_value=True)
    def test_legacy_daemon_requires_explicit_migration(self, *_):
        with self.assertRaisesRegex(SettingsError, "legacy"):
            build_settings(
                Platform("macos", "brew", "arm64"), FakeRunner(), ["wireless"], None
            )

    @patch("unleashlib.settings.os.geteuid", return_value=1000)
    @patch("unleashlib.settings.Path.exists", return_value=False)
    def test_gpu_bounds_checked_before_any_write(self, *_):
        runner = FakeRunner(
            {
                ("sysctl", "-n", "hw.memsize"): (0, str(16 * 1024**3)),
                ("sysctl", "-n", "iogpu.wired_limit_mb"): (0, "8000"),
            },
            available={"sysctl", "sudo"},
        )
        for limit in (0, -1, 16000):
            with self.assertRaises(SettingsError):
                build_settings(Platform("macos", "brew", "arm64"), runner, [], limit)
        settings = build_settings(Platform("macos", "brew", "arm64"), runner, [], 10000)
        self.assertEqual(settings[0].read(), 8000)
        self.assertEqual(settings[0].desired, 10000)
        self.assertFalse(any("-w" in c for c in runner.calls))

    @patch("unleashlib.settings.os.geteuid", return_value=1000)
    @patch("unleashlib.settings.Path.exists", return_value=False)
    def test_mac_wireless_flags_and_restore_write(self, *_):
        responses = {
            ("ifconfig", "awdl0"): (0, "awdl0: flags=89a3<UP,BROADCAST,RUNNING>"),
            ("ifconfig", "llw0"): (0, "llw0: flags=8863<UP,RUNNING>"),
        }
        runner = FakeRunner(responses, available={"ifconfig", "sudo"})
        settings = build_settings(
            Platform("macos", "brew", "arm64"), runner, ["wireless"], None
        )
        self.assertIs(settings[0].read(), True)
        settings[0].write(False)
        settings[0].write(True)
        self.assertIn(["sudo", "ifconfig", "awdl0", "down"], runner.calls)
        self.assertIn(["sudo", "ifconfig", "awdl0", "up"], runner.calls)

    @patch("unleashlib.settings.os.geteuid", return_value=1000)
    @patch("unleashlib.settings.Path.exists", return_value=False)
    def test_mac_power_only_changes_supported_charger_values(self, *_):
        text = "Battery Power:\n sleep 15\n displaysleep 10\nAC Power:\n sleep 30\n displaysleep 10\n"
        runner = FakeRunner(
            {("pmset", "-g", "custom"): (0, text)}, available={"pmset", "sudo"}
        )
        settings = build_settings(
            Platform("macos", "brew", "arm64"), runner, ["power"], None
        )
        self.assertEqual([s.read() for s in settings], [30, 10])
        settings[0].write(0)
        self.assertIn(["sudo", "pmset", "-c", "sleep", "0"], runner.calls)
        self.assertFalse(any("-b" in command for command in runner.calls))

    @patch("unleashlib.settings.os.geteuid", return_value=1000)
    @patch("unleashlib.settings.Path.exists", return_value=False)
    def test_mac_service_overrides_and_system_preference(self, *_):
        responses = {
            ("launchctl", "print-disabled", "system"): (
                0,
                '"com.apple.analyticsd" => false\n"com.apple.diagnosticd" => true',
            ),
            (
                "defaults",
                "export",
                "/Library/Preferences/com.apple.mDNSResponder.plist",
                "-",
            ): (0, plistlib.dumps({}).decode()),
        }
        runner = FakeRunner(responses, available={"launchctl", "defaults", "sudo"})
        settings = build_settings(
            Platform("macos", "brew", "arm64"), runner, ["services"], None
        )
        self.assertEqual([s.read() for s in settings], [False, True, None])
        settings[0].write(True)
        settings[2].write(True)
        self.assertIn(
            ["sudo", "launchctl", "disable", "system/com.apple.analyticsd"],
            runner.calls,
        )
        self.assertIn(
            [
                "sudo",
                "defaults",
                "write",
                "/Library/Preferences/com.apple.mDNSResponder.plist",
                "NoMulticastAdvertisements",
                "-bool",
                "true",
            ],
            runner.calls,
        )

    @patch("unleashlib.settings.os.geteuid", return_value=1000)
    @patch("unleashlib.settings.Path.exists", return_value=False)
    def test_wireless_writer_rejects_invalid_snapshot_without_mutation(self, *_):
        runner = FakeRunner(
            {
                ("ifconfig", "awdl0"): (0, "awdl0: flags=8863<UP,RUNNING>"),
                ("ifconfig", "llw0"): (0, "llw0: flags=8863<UP,RUNNING>"),
            },
            available={"ifconfig", "sudo"},
        )
        setting = build_settings(
            Platform("macos", "brew", "arm64"), runner, ["wireless"], None
        )[0]
        count = len(runner.calls)
        with self.assertRaises(SettingsError):
            setting.write(None)
        self.assertEqual(len(runner.calls), count)
