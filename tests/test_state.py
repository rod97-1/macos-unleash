import json
import os
from pathlib import Path
import tempfile
import unittest
from unleashlib.platforms import Platform
from unleashlib.settings import Setting
from unleashlib.state import StateError, StateStore


class StateTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'state'
        self.store=StateStore(self.path,Platform('debian','apt','x86_64'))
        self.value={'example':None}
        self.setting=Setting('example','Example',lambda:self.value['example'],lambda v:self.value.__setitem__('example',v),False)

    def test_read_does_not_create_directory(self):
        self.assertEqual(self.store.load()['settings'],{})
        self.assertFalse(self.path.exists())

    def test_apply_and_restore_absent_value(self):
        run=self.store.apply([self.setting])
        self.assertIs(self.value['example'],False)
        self.store.restore({'example':self.setting},run)
        self.assertIsNone(self.value['example'])
        self.assertEqual(self.store.load()['settings'],{})
        self.assertEqual(self.path.stat().st_mode & 0o777,0o700)
        self.assertEqual((self.path/'state.json').stat().st_mode & 0o777,0o600)

    def test_repeated_apply_retains_original_and_run(self):
        first=self.store.apply([self.setting])
        self.assertIsNone(self.store.apply([self.setting]))
        self.setting.desired=True
        second=self.store.apply([self.setting])
        entry=self.store.load()['settings']['example']
        self.assertIsNone(entry['before'])
        with self.assertRaisesRegex(StateError,'later run'):
            self.store.restore({'example':self.setting},first)
        self.store.restore({'example':self.setting},second)
        self.assertIsNone(self.value['example'])

    def test_external_change_blocks_restore_and_apply(self):
        run=self.store.apply([self.setting])
        self.value['example']='user change'
        with self.assertRaisesRegex(StateError,'conflict'):
            self.store.restore({'example':self.setting},run)
        with self.assertRaisesRegex(StateError,'conflict'):
            self.store.apply([self.setting])
        self.assertEqual(self.value['example'],'user change')

    def test_failed_write_has_recoverable_pending_snapshot(self):
        def fail(value):
            raise RuntimeError('write failed')
        self.setting.write=fail
        with self.assertRaisesRegex(RuntimeError,'write failed'):
            self.store.apply([self.setting])
        state=self.store.load()
        self.assertIsNone(state['settings']['example']['before'])
        self.store.restore({'example':self.setting},next(iter(state['runs'])))
        self.assertEqual(self.store.load()['settings'],{})

    def test_restore_validates_all_settings_before_any_write(self):
        other=Setting('other','Other',lambda:self.value.get('other'),lambda v:self.value.__setitem__('other',v),10)
        run=self.store.apply([self.setting,other])
        self.value['other']=99
        with self.assertRaises(StateError):
            self.store.restore({'example':self.setting,'other':other},run)
        self.assertIs(self.value['example'],False)

    def test_invalid_state_and_wrong_context_are_rejected(self):
        self.store.apply([self.setting])
        original=json.loads((self.path/'state.json').read_text())
        for key,value in [('version',99),('uid',os.getuid()+1),('platform','fedora:x86_64')]:
            data={**original,key:value}
            (self.path/'state.json').write_text(json.dumps(data))
            with self.assertRaises(StateError):self.store.load()
        (self.path/'state.json').write_text('{invalid')
        with self.assertRaises(StateError):self.store.load()

    def test_journal_cannot_supply_commands_or_unknown_setting_handlers(self):
        run=self.store.apply([self.setting])
        with self.assertRaisesRegex(StateError,'Unknown'):
            self.store.restore({},run)
        data=self.store.load()
        data['settings']['example']['argv']=['touch','/tmp/should-never-run']
        (self.path/'state.json').write_text(json.dumps(data))
        with self.assertRaises(StateError):self.store.load()

    def test_symlink_and_open_permissions_are_rejected(self):
        self.path.symlink_to(self.temp.name,target_is_directory=True)
        with self.assertRaises(StateError):self.store.load()
        self.path.unlink()
        self.store.apply([self.setting])
        (self.path/'state.json').chmod(0o644)
        with self.assertRaises(StateError):self.store.load()

    def test_run_identifier_is_validated(self):
        self.store.apply([self.setting])
        with self.assertRaises(StateError):self.store.restore({'example':self.setting},'../../other')
