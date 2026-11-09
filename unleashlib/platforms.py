"""Detect only explicitly supported operating systems."""
from dataclasses import dataclass
import platform
from pathlib import Path
import shlex


class PlatformError(ValueError):
    pass


@dataclass(frozen=True)
class Platform:
    name: str
    manager: str
    arch: str

    @property
    def identity(self):
        return f'{self.name}:{self.arch}'


def read_release(path=Path('/etc/os-release')):
    values = {}
    try:
        for line in path.read_text().splitlines():
            if '=' not in line or line.lstrip().startswith('#'):
                continue
            key, value = line.split('=', 1)
            parts = shlex.split(value, comments=True)
            if len(parts) == 1:
                values[key] = parts[0]
    except (OSError, ValueError) as exc:
        raise PlatformError(f'Cannot read operating system identity: {exc}') from exc
    return values


def detect_platform(system=None, machine=None, release=None):
    system = platform.system() if system is None else system
    machine = platform.machine().lower() if machine is None else machine.lower()
    if system == 'Windows':
        raise PlatformError('Windows support is deferred until the Linux milestone is complete.')
    if system == 'Darwin':
        if machine != 'arm64':
            raise PlatformError('macOS requires a native Apple Silicon (arm64) Python interpreter.')
        return Platform('macos', 'brew', 'arm64')
    if system != 'Linux':
        raise PlatformError(f'Unsupported operating system: {system}')
    if machine not in ('x86_64', 'aarch64', 'arm64'):
        raise PlatformError(f'Unsupported Linux architecture: {machine}')
    release = read_release() if release is None else release
    name = release.get('ID', '')
    managers = {'ubuntu': 'apt', 'debian': 'apt', 'fedora': 'dnf'}
    if name not in managers:
        raise PlatformError('Supported Linux distributions: Ubuntu, Debian, Fedora. Detected ID: ' + repr(name))
    return Platform(name, managers[name], 'arm64' if machine in ('arm64', 'aarch64') else 'x86_64')
