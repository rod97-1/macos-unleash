"""Load and select a validated, explicit tool catalog."""
from dataclasses import dataclass
import json
from pathlib import Path
import re

PROFILES = ('core', 'dev', 'desktop', 'ai', 'full')
IDENTIFIER = re.compile(r'^[A-Za-z0-9][A-Za-z0-9+@._/-]*$')


class CatalogError(ValueError):
    pass


@dataclass(frozen=True)
class Tool:
    id: str
    profiles: list
    packages: dict
    command: str = ''
    cask: bool = False
    guidance: str = ''


def load_catalog(path=None):
    path = Path(path) if path else Path(__file__).with_name('catalog.json')
    try:
        entries = json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        raise CatalogError(f'Cannot read tool catalog: {exc}') from exc
    result = {}
    if not isinstance(entries, list):
        raise CatalogError('Tool catalog must be a list.')
    for entry in entries:
        try:
            tool = Tool(**entry)
            if not IDENTIFIER.fullmatch(tool.id) or tool.id in result:
                raise ValueError('invalid or duplicate tool ID')
            if not isinstance(tool.profiles, list) or any(p not in PROFILES for p in tool.profiles):
                raise ValueError('invalid profiles')
            if not isinstance(tool.packages, dict) or any(k not in ('apt', 'dnf', 'brew') for k in tool.packages):
                raise ValueError('invalid package manager')
            for packages in tool.packages.values():
                if not isinstance(packages, list) or not packages:
                    raise ValueError('package list must be nonempty')
                if any(not isinstance(p, str) or not IDENTIFIER.fullmatch(p) or '..' in p for p in packages):
                    raise ValueError('invalid package identifier')
            if not isinstance(tool.command, str) or (tool.command and not IDENTIFIER.fullmatch(tool.command)):
                raise ValueError('invalid executable')
            if not isinstance(tool.cask, bool) or not isinstance(tool.guidance, str):
                raise ValueError('invalid metadata')
        except (TypeError, ValueError, AttributeError) as exc:
            raise CatalogError(f'Invalid tool entry: {exc}') from exc
        result[tool.id] = tool
    return result


def select_tools(catalog, profiles, include, exclude):
    for profile in profiles:
        if profile not in PROFILES:
            raise CatalogError(f'Unknown profile: {profile}')
    for name in [*include, *exclude]:
        if name not in catalog:
            raise CatalogError(f'Unknown tool: {name}')
    if not profiles and not include:
        profiles = ['core']
    return [tool for tool in catalog.values()
            if (set(profiles).intersection(tool.profiles) or tool.id in include)
            and tool.id not in exclude]
