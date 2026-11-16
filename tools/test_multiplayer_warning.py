import unittest

from multiplayer_warning import OPTION_PATH, load_option


class MultiplayerWarningTests(unittest.TestCase):
    def test_author_can_replace_or_remove_native_options(self):
        current = {"overrides": [{"path": "options.txt", "sha256": "original"}]}
        replacement = {"overrides": [{"path": "options.txt", "sha256": "updated"}]}
        without_native_options = {"overrides": []}
        expected = load_option(current)

        for author in (replacement, without_native_options):
            with self.subTest(author=author):
                self.assertEqual(expected, load_option(author))
        self.assertEqual(OPTION_PATH, expected[0]["path"])
        self.assertEqual(b"!skipMultiplayerWarning:true\n", expected[1])

    def test_detects_collision_with_launcher_policy_file(self):
        with self.assertRaisesRegex(ValueError, "author's new launcher options file"):
            load_option({"overrides": [{"path": OPTION_PATH.upper()}]})
