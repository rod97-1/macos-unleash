import re
import unittest
from pathlib import Path
from unleashlib.catalog import CatalogError, load_catalog, select_tools


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.catalog = load_catalog()

    def test_core_is_default_and_supported_on_linux(self):
        selected = select_tools(self.catalog, [], [], [])
        self.assertIn('git', [t.id for t in selected])
        for tool in selected:
            self.assertTrue(tool.packages['apt'])
            self.assertTrue(tool.packages['dnf'])

    def test_dev_is_complete_from_distribution_repositories(self):
        for tool in select_tools(self.catalog, ['dev'], [], []):
            self.assertTrue(tool.packages.get('apt'))
            self.assertTrue(tool.packages.get('dnf'))

    def test_selection_deduplicates_and_excludes(self):
        selected = select_tools(self.catalog, ['core', 'dev'], ['git'], ['git'])
        ids = [t.id for t in selected]
        self.assertNotIn('git', ids)
        self.assertEqual(len(ids), len(set(ids)))
        self.assertIn('node', ids)

    def test_individual_selection_does_not_add_core_implicitly(self):
        self.assertEqual([t.id for t in select_tools(self.catalog, [], ['jq'], [])], ['jq'])

    def test_invalid_selections_fail(self):
        for args in [(['unknown'], [], []), ([], ['git;whoami'], []), ([], [], ['missing'])]:
            with self.assertRaises(CatalogError):
                select_tools(self.catalog, *args)

    def test_full_mac_catalog_exactly_matches_brewfile(self):
        expected = set(re.findall(r'^(brew|cask) "([^"]+)"', Path('Brewfile').read_text(), re.M))
        actual = {(('cask' if t.cask else 'brew'), p)
                  for t in select_tools(self.catalog, ['full'], [], [])
                  for p in t.packages.get('brew', [])}
        self.assertEqual(actual, expected)

    def test_catalog_package_identifiers_are_not_options_or_shell_fragments(self):
        for tool in self.catalog.values():
            for packages in tool.packages.values():
                for name in packages:
                    self.assertRegex(name, r'^[A-Za-z0-9][A-Za-z0-9+@._/-]*$')
