import subprocess
import sys
import unittest
from unleashlib.catalog import load_catalog
from unleashlib.platforms import Platform
from unleashlib.packages import PackageManager, PackageError
from unleashlib.runner import Runner, CommandError
from helpers import FakeRunner


class PackageTests(unittest.TestCase):
    def setUp(self):
        self.tools = load_catalog()

    def test_plan_is_read_only_and_quotes_each_package_as_argument(self):
        runner = FakeRunner()
        manager = PackageManager(Platform('debian','apt','x86_64'),runner,euid=1000)
        commands = manager.commands([self.tools['node'],self.tools['git']])
        self.assertEqual(commands, [['sudo','apt-get','update'],['sudo','apt-get','install','-y','--no-install-recommends','nodejs','npm','git']])
        self.assertFalse(runner.calls)

    def test_dnf_and_brew_commands(self):
        dnf = PackageManager(Platform('fedora','dnf','x86_64'), FakeRunner(), euid=0)
        self.assertEqual(dnf.commands([self.tools['git']]), [['dnf','install','-y','--setopt=install_weak_deps=False','git']])
        brew = PackageManager(Platform('macos','brew','arm64'), FakeRunner(),euid=1000)
        self.assertEqual(brew.commands([self.tools['git'],self.tools['firefox']]), [['brew','install','git'],['brew','install','--cask','firefox']])

    def test_already_installed_packages_are_not_reinstalled(self):
        runner=FakeRunner({('dpkg-query','-W','-f=${db:Status-Status}','git'):(0,'installed')})
        manager=PackageManager(Platform('debian','apt','x86_64'),runner,euid=0)
        self.assertTrue(manager.installed(self.tools['git']))
        self.assertEqual(manager.install([self.tools['git']]), [])
        self.assertFalse(any('apt-get' in c for c in runner.calls))

    def test_external_prerequisite_blocks_all_installation(self):
        runner=FakeRunner()
        manager=PackageManager(Platform('debian','apt','x86_64'),runner,euid=0)
        with self.assertRaisesRegex(PackageError,'Ollama'):
            manager.install([self.tools['git'],self.tools['ollama']])
        self.assertFalse(any('apt-get' in c for c in runner.calls))

    def test_existing_external_tool_is_recognized(self):
        manager=PackageManager(Platform('debian','apt','x86_64'),FakeRunner(available={'ollama'}),euid=0)
        self.assertTrue(manager.installed(self.tools['ollama']))

    def test_unavailable_package_stops_before_install(self):
        responses={('dpkg-query','-W','-f=${db:Status-Status}','git'):(1,''),('apt-cache','show','git'):(100,'No packages found')}
        runner=FakeRunner(responses)
        manager=PackageManager(Platform('debian','apt','x86_64'),runner,euid=0)
        with self.assertRaisesRegex(PackageError,'unavailable'):
            manager.install([self.tools['git']])
        self.assertFalse(any('install' in c for c in runner.calls))

    def test_install_failure_preserves_exit_status(self):
        command=('apt-get','install','-y','--no-install-recommends','git')
        runner=FakeRunner({('dpkg-query','-W','-f=${db:Status-Status}','git'):(1,''),('apt-cache','show','git'):(0,'Package: git'),command:(42,'disk full')})
        with self.assertRaises(CommandError) as error:
            PackageManager(Platform('debian','apt','x86_64'),runner,euid=0).install([self.tools['git']])
        self.assertEqual(error.exception.code,42)

    def test_actual_runner_preserves_argument_boundaries(self):
        result=Runner().run([sys.executable,'-c','import sys; print(sys.argv[1])','hello; $HOME'])
        self.assertEqual(result.stdout.strip(),'hello; $HOME')
        with self.assertRaises(CommandError) as error:
            Runner().run([sys.executable,'-c','raise SystemExit(23)'])
        self.assertEqual(error.exception.code,23)

    def test_missing_executable_is_actionable(self):
        with self.assertRaises(CommandError) as error:
            Runner().run(['/nonexistent/unleash-command'])
        self.assertEqual(error.exception.code,127)
