import json
import unittest

from review_author_update import MENU_PATH, PACK, verify_title_menu


class TitleMenuTests(unittest.TestCase):
    def setUp(self):
        self.author = json.loads((PACK / "tools/upstream-client-lock.json").read_text(encoding="utf-8"))
        self.rows = self.author["overrides"]
        self.menu = next(row for row in self.rows if row["path"] == MENU_PATH)

    def test_locked_menu_is_accepted(self):
        verify_title_menu(self.author)

    def test_changed_menu_is_rejected(self):
        self.menu["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "author title layout"):
            verify_title_menu(self.author)

    def test_missing_menu_is_rejected(self):
        self.rows.remove(self.menu)
        with self.assertRaisesRegex(ValueError, "author title layout"):
            verify_title_menu(self.author)

    def test_case_variant_duplicate_is_rejected(self):
        self.rows.append({**self.menu, "path": MENU_PATH.upper()})
        with self.assertRaisesRegex(ValueError, "author title layout"):
            verify_title_menu(self.author)


if __name__ == "__main__":
    unittest.main()
