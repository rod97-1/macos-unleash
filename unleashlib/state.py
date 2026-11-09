"""Versioned, locked recovery data. Journal data never supplies executable commands."""
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import re
import stat
import tempfile
import uuid


class StateError(RuntimeError):
    pass


def _scalar(value):
    return value is None or type(value) in (bool, int, str) or (type(value) is float and math.isfinite(value))


class StateStore:
    def __init__(self, path, platform):
        self.path = Path(path).expanduser().absolute()
        self.platform = platform

    def empty(self):
        return {'version': 1, 'platform': self.platform.identity, 'uid': os.getuid(), 'runs': {}, 'settings': {}}

    def _secure(self, path, directory=False):
        info = path.lstat()
        if stat.S_ISLNK(info.st_mode) or info.st_uid != os.getuid():
            raise StateError(f'Recovery path must be owned by this user and not a symlink: {path}')
        expected = stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)
        if not expected or stat.S_IMODE(info.st_mode) != (0o700 if directory else 0o600):
            raise StateError(f'Recovery permissions must be {"700" if directory else "600"}: {path}')

    def _validate(self, data):
        if not isinstance(data, dict) or set(data) != {'version', 'platform', 'uid', 'runs', 'settings'}:
            raise StateError('Invalid recovery journal schema.')
        if data['version'] != 1 or data['platform'] != self.platform.identity or data['uid'] != os.getuid():
            raise StateError('Recovery journal has the wrong version, platform, or user.')
        runs, settings = data['runs'], data['settings']
        if not isinstance(runs, dict) or not isinstance(settings, dict):
            raise StateError('Invalid recovery records.')
        for run_id, ids in runs.items():
            if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', run_id) or not isinstance(ids, list) or len(ids) != len(set(ids)):
                raise StateError('Invalid recovery run identifier or setting list.')
            if any(not isinstance(sid, str) or not re.fullmatch(r'[a-z][a-z0-9_.-]{0,100}', sid) for sid in ids):
                raise StateError('Invalid setting identifier.')
        for sid, entry in settings.items():
            if not re.fullmatch(r'[a-z][a-z0-9_.-]{0,100}', sid) or not isinstance(entry, dict) or set(entry) != {'before', 'after', 'run'}:
                raise StateError('Invalid setting record.')
            if not _scalar(entry['before']) or not _scalar(entry['after']) or entry['run'] not in runs or sid not in runs[entry['run']]:
                raise StateError('Invalid setting snapshot.')
        return data

    def load(self):
        if self.path.is_symlink():
            raise StateError('Recovery directory cannot be a symlink.')
        if not self.path.exists():
            return self.empty()
        self._secure(self.path, directory=True)
        file = self.path / 'state.json'
        if not file.exists() and not file.is_symlink():
            return self.empty()
        self._secure(file)
        if file.stat().st_size > 1024 * 1024:
            raise StateError('Recovery journal is too large.')
        try:
            fd = os.open(file, os.O_RDONLY | os.O_NOFOLLOW)
            with os.fdopen(fd) as stream:
                return self._validate(json.load(stream))
        except (ValueError, TypeError, OSError) as exc:
            raise StateError(f'Cannot read recovery journal: {exc}') from exc

    @contextmanager
    def locked(self):
        import fcntl
        self.path.mkdir(mode=0o700, parents=True, exist_ok=True)
        self._secure(self.path, directory=True)
        file = self.path / '.lock'
        try:
            fd = os.open(file, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        except OSError as exc:
            raise StateError(f'Cannot open recovery lock: {exc}') from exc
        try:
            self._secure(file)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise StateError('Another operation holds the recovery lock.') from exc
            yield
        finally:
            os.close(fd)

    def _save(self, data):
        self._validate(data)
        fd, name = tempfile.mkstemp(prefix='.state-', dir=self.path)
        try:
            with os.fdopen(fd, 'w') as stream:
                os.fchmod(stream.fileno(), 0o600)
                json.dump(data, stream, indent=2, sort_keys=True, allow_nan=False)
                stream.write('\n')
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name, self.path / 'state.json')
        finally:
            if os.path.exists(name):
                os.unlink(name)

    def apply(self, settings):
        with self.locked():
            data = self.load()
            pending = []
            for setting in settings:
                current = setting.read()
                entry = data['settings'].get(setting.id)
                if entry and current != entry['after'] and current != entry['before']:
                    raise StateError(f'Setting conflict: {setting.id} changed outside this launcher.')
                if current != setting.desired:
                    pending.append((setting, current))
            if not pending:
                return None
            run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ-') + uuid.uuid4().hex[:12]
            data['runs'][run_id] = []
            for setting, current in pending:
                if setting.read() != current:
                    raise StateError(f'Setting conflict: {setting.id} changed during apply.')
                entry = data['settings'].get(setting.id)
                original = entry['before'] if entry else current
                data['runs'][run_id].append(setting.id)
                data['settings'][setting.id] = {'before': original, 'after': setting.desired, 'run': run_id}
                self._save(data)  # Persist the original before attempting the write.
                setting.write(setting.desired)
                if setting.read() != setting.desired:
                    raise StateError(f'Setting verification failed: {setting.id}; recovery journal retained.')
            return run_id

    def restore(self, settings_by_id, run_id=None):
        with self.locked():
            data = self.load()
            if not data['runs']:
                raise StateError('No recovery runs found.')
            if run_id is None:
                run_id = sorted(data['runs'])[-1]
            if not isinstance(run_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', run_id) or run_id not in data['runs']:
                raise StateError('Unknown recovery run.')
            pending = []
            for sid in data['runs'][run_id]:
                entry = data['settings'].get(sid)
                if entry is None:
                    continue
                if entry['run'] != run_id:
                    raise StateError(f'A later run owns {sid}; restore that later run first.')
                if sid not in settings_by_id:
                    raise StateError(f'Unknown setting handler: {sid}')
                setting = settings_by_id[sid]
                current = setting.read()
                if current != entry['after'] and current != entry['before']:
                    raise StateError(f'Restore conflict: {sid} changed outside this launcher.')
                pending.append((setting, entry, current))
            for setting, entry, current in reversed(pending):
                if setting.read() != current:
                    raise StateError(f'Restore conflict: {setting.id} changed during recovery.')
                if current != entry['before']:
                    setting.write(entry['before'])
                    if setting.read() != entry['before']:
                        raise StateError(f'Restore verification failed: {setting.id}')
                del data['settings'][setting.id]
                self._save(data)
            del data['runs'][run_id]
            self._save(data)
            return len(pending)
