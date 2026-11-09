import plistlib
import unittest
from unittest.mock import patch
from unleashlib.platforms import Platform
from unleashlib.settings import SettingsError, build_settings
from helpers import FakeRunner


class SettingsTests(unittest.TestCase):
    def test_no_tuning_means_no_commands(self):
        runner=FakeRunner()
        self.assertEqual(build_settings(Platform('debian','apt','x86_64'),runner,[],None),[])
        self.assertFalse(runner.calls)

    @patch('unleashlib.settings.os.geteuid',return_value=1000)
    @patch.dict('os.environ',{'DBUS_SESSION_BUS_ADDRESS':'test'})
    def test_gnome_animation_snapshot_and_write(self,_):
        runner=FakeRunner({('gsettings','writable','org.gnome.desktop.interface','enable-animations'):(0,'true'),('gsettings','get','org.gnome.desktop.interface','enable-animations'):(0,'true')},available={'gsettings'})
        settings=build_settings(Platform('debian','apt','x86_64'),runner,['desktop'],None)
        self.assertEqual(settings[0].read(),True)
        self.assertEqual(settings[0].desired,False)
        settings[0].write(False)
        self.assertIn(['gsettings','set','org.gnome.desktop.interface','enable-animations','false'],runner.calls)

    @patch('unleashlib.settings.os.geteuid',return_value=1000)
    def test_headless_desktop_is_rejected(self,_):
        with patch.dict('os.environ',{},clear=True),self.assertRaisesRegex(SettingsError,'desktop session'):
            build_settings(Platform('debian','apt','x86_64'),FakeRunner(available={'gsettings'}),['desktop'],None)

    @patch('unleashlib.settings.os.geteuid',return_value=1000)
    def test_power_requires_performance_capability(self,_):
        runner=FakeRunner({('powerprofilesctl','list'):(0,'balanced:\npower-saver:')},available={'powerprofilesctl'})
        with self.assertRaisesRegex(SettingsError,'performance'):
            build_settings(Platform('fedora','dnf','x86_64'),runner,['power'],None)

    @patch('unleashlib.settings.os.geteuid',return_value=1000)
    def test_linux_does_not_accept_mac_wireless_group(self,_):
        with self.assertRaisesRegex(SettingsError,'macOS'):
            build_settings(Platform('debian','apt','x86_64'),FakeRunner(),['wireless'],None)

    @patch('unleashlib.settings.os.geteuid',return_value=1000)
    @patch('unleashlib.settings.Path.exists',return_value=False)
    def test_mac_preferences_retain_original_types(self,*_):
        xml=plistlib.dumps({'magnification':True}).decode()
        runner=FakeRunner({('defaults','export','com.apple.dock','-'):(0,xml),
            ('defaults','export','com.apple.finder','-'):(0,plistlib.dumps({}).decode()),
            ('defaults','export','NSGlobalDomain','-'):(0,plistlib.dumps({}).decode())},available={'defaults'})
        settings=build_settings(Platform('macos','brew','arm64'),runner,['desktop'],None)
        setting=next(s for s in settings if s.id=='mac.dock.magnification')
        self.assertIs(setting.read(),True)
        setting.write(True)
        self.assertIn(['defaults','write','com.apple.dock','magnification','-bool','true'],runner.calls)
        setting.write(None)
        self.assertIn(['defaults','delete','com.apple.dock','magnification'],runner.calls)

    @patch('unleashlib.settings.os.geteuid',return_value=1000)
    @patch('unleashlib.settings.Path.exists',return_value=True)
    def test_legacy_daemon_requires_explicit_migration(self,*_):
        with self.assertRaisesRegex(SettingsError,'legacy'):
            build_settings(Platform('macos','brew','arm64'),FakeRunner(),['wireless'],None)

    @patch('unleashlib.settings.os.geteuid',return_value=1000)
    @patch('unleashlib.settings.Path.exists',return_value=False)
    def test_gpu_bounds_checked_before_any_write(self,*_):
        runner=FakeRunner({('sysctl','-n','hw.memsize'):(0,str(16*1024**3)),('sysctl','-n','iogpu.wired_limit_mb'):(0,'8000')},available={'sysctl','sudo'})
        for limit in (0,-1,16000):
            with self.assertRaises(SettingsError):
                build_settings(Platform('macos','brew','arm64'),runner,[],limit)
        settings=build_settings(Platform('macos','brew','arm64'),runner,[],10000)
        self.assertEqual(settings[0].read(),8000)
        self.assertEqual(settings[0].desired,10000)
        self.assertFalse(any('-w' in c for c in runner.calls))
