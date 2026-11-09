import unittest
from unleashlib.platforms import PlatformError, detect_platform


class PlatformTests(unittest.TestCase):
    def test_supported_linux_families(self):
        for name, manager in [('ubuntu', 'apt'), ('debian', 'apt'), ('fedora', 'dnf')]:
            with self.subTest(name=name):
                self.assertEqual(detect_platform('Linux', 'x86_64', {'ID': name}).manager, manager)

    def test_mac_requires_native_arm64(self):
        self.assertEqual(detect_platform('Darwin', 'arm64', {}).name, 'macos')
        with self.assertRaisesRegex(PlatformError, 'Apple Silicon'):
            detect_platform('Darwin', 'x86_64', {})

    def test_windows_is_deferred(self):
        with self.assertRaisesRegex(PlatformError, 'Windows.*deferred'):
            detect_platform('Windows', 'AMD64', {})

    def test_unknown_distribution_is_not_guessed_from_id_like(self):
        for release in [{}, {'ID': 'mint', 'ID_LIKE': 'ubuntu'}, {'ID': 'ubuntu; touch /tmp/pwn'}]:
            with self.assertRaises(PlatformError):
                detect_platform('Linux', 'x86_64', release)

    def test_unsupported_architecture_fails(self):
        with self.assertRaises(PlatformError):
            detect_platform('Linux', 'mips', {'ID': 'debian'})
