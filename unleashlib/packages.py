"""Native package inspection, read-only plans, and explicit installation."""
import os
from .runner import CommandError


class PackageError(RuntimeError):
    pass


class PackageManager:
    def __init__(self, platform, runner, euid=None):
        self.platform = platform
        self.runner = runner
        self.euid = os.geteuid() if euid is None else euid

    def packages(self, tool):
        return tool.packages.get(self.platform.name, tool.packages.get(self.platform.manager, []))

    def elevate(self, argv):
        return ['sudo', *argv] if self.euid != 0 and self.platform.manager != 'brew' else argv

    @property
    def required_commands(self):
        return {'apt': ['apt-get', 'apt-cache', 'dpkg-query'], 'dnf': ['dnf', 'rpm'], 'brew': ['brew']}[self.platform.manager]

    def installed(self, tool):
        packages = self.packages(tool)
        if not packages:
            return bool(tool.command and self.runner.which(tool.command))
        for name in packages:
            if self.platform.manager == 'apt':
                result = self.runner.run(['dpkg-query', '-W', '-f=${db:Status-Status}', name], check=False)
                if result.returncode or result.stdout.strip() != 'installed':
                    return False
            elif self.platform.manager == 'dnf':
                if self.runner.run(['rpm', '-q', name], check=False).returncode:
                    return False
            else:
                kind = '--cask' if tool.cask else '--formula'
                result = self.runner.run(['brew', 'list', kind, '--versions', name], check=False)
                if result.returncode or not result.stdout.strip():
                    return False
        return True

    def commands(self, tools):
        packages = list(dict.fromkeys(p for t in tools for p in self.packages(t)))
        if not packages:
            return []
        if self.platform.manager == 'apt':
            return [self.elevate(['apt-get', 'update']), self.elevate(['apt-get', 'install', '-y', '--no-install-recommends', *packages])]
        if self.platform.manager == 'dnf':
            return [self.elevate(['dnf', 'install', '-y', '--setopt=install_weak_deps=False', *packages])]
        commands = []
        for cask in (False, True):
            names = list(dict.fromkeys(p for t in tools if t.cask == cask for p in self.packages(t)))
            if names:
                commands.append(['brew', 'install', *(['--cask'] if cask else []), *names])
        return commands

    def missing(self, tools):
        return [tool for tool in tools if not self.installed(tool)]

    def install(self, tools):
        missing = self.missing(tools)
        for tool in missing:
            if not self.packages(tool):
                raise PackageError(f'{tool.id}: manual prerequisite. {tool.guidance}')
        if not missing:
            return []
        commands = self.commands(missing)
        if self.platform.manager == 'brew' and self.euid == 0:
            raise PackageError('Run Homebrew as your normal user, not root.')
        if self.euid != 0 and self.platform.manager != 'brew' and not self.runner.which('sudo'):
            raise PackageError('sudo is required to install system packages from a normal account.')
        # Refresh APT indexes before checking availability. Never upgrade the system.
        if self.platform.manager == 'apt':
            self.runner.run(commands.pop(0), live=True)
        for tool in missing:
            for name in self.packages(tool):
                if self.platform.manager == 'apt':
                    command = ['apt-cache', 'show', name]
                elif self.platform.manager == 'dnf':
                    command = ['dnf', '-q', 'list', '--available', name]
                else:
                    command = ['brew', 'info', '--cask' if tool.cask else '--formula', name]
                result = self.runner.run(command, check=False)
                if result.returncode or (self.platform.manager == 'apt' and 'Package:' not in result.stdout):
                    raise PackageError(f'Package unavailable: {name}. Resolve repository availability before retrying. {result.stderr.strip()}')
        for command in commands:
            self.runner.run(command, live=True)
        still_missing = self.missing(missing)
        if still_missing:
            raise PackageError('Installation returned success but verification failed: ' + ', '.join(t.id for t in still_missing))
        return [t.id for t in missing]
