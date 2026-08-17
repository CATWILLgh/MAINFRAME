#!/usr/bin/env python3
"""Verify every user-facing hub-page string is translatable in both languages.

The page routes all display text through `t("…")` / `f("…", …)`. This test walks
those call sites and fails when a key is missing from the Russian catalogue, so a
newly added English literal cannot silently ship as an untranslatable island.
"""

import pathlib
import re
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
ASSETS = ROOT / "tools" / "hub_page_assets"

# A JavaScript double-quoted literal, allowing escaped quotes.
_LITERAL = r'"((?:[^"\\]|\\.)*)"'
_CALL = re.compile(r'(?<![A-Za-z0-9_$.])([tf])\(\s*' + _LITERAL)
_ENTRY = re.compile(r'^\s*' + _LITERAL + r'\s*:', re.M)
_PLACEHOLDER = re.compile(r"\{(\w+)\}")


def _unescape(text):
    return text.replace('\\"', '"').replace("\\\\", "\\").replace("\\n", "\n")


def _catalogue():
    source = (ASSETS / "i18n.js").read_text(encoding="utf-8")
    body = source[source.index("window.HUB_STRINGS_RU"):]
    keys, values = [], []
    for match in re.finditer(
        r'^\s*' + _LITERAL + r'\s*:\s*\n?\s*' + _LITERAL + r'\s*,', body, re.M
    ):
        keys.append(_unescape(match.group(1)))
        values.append(_unescape(match.group(2)))
    return dict(zip(keys, values))


def _used_keys():
    source = (ASSETS / "app.js").read_text(encoding="utf-8")
    return {_unescape(match.group(2)) for match in _CALL.finditer(source)}


class HubPageLocalization(unittest.TestCase):
    def setUp(self):
        self.catalogue = _catalogue()
        self.used = _used_keys()

    def test_catalogue_parses(self):
        self.assertGreater(len(self.catalogue), 100, "catalogue failed to parse")

    def test_every_display_string_is_translated(self):
        # Dynamic keys are values the report supplies (an evidence flag, a job
        # status); they are translated through the same catalogue when present,
        # and a raw literal here would be a hard-coded English string instead.
        missing = sorted(key for key in self.used if key not in self.catalogue)
        self.assertEqual(missing, [], f"missing Russian translations: {missing}")

    def test_placeholders_survive_translation(self):
        broken = []
        for key, value in self.catalogue.items():
            if set(_PLACEHOLDER.findall(key)) != set(_PLACEHOLDER.findall(value)):
                broken.append(key)
        self.assertEqual(broken, [], f"placeholder mismatch: {broken}")

    def test_no_empty_translation(self):
        empty = sorted(key for key, value in self.catalogue.items() if not value.strip())
        self.assertEqual(empty, [], f"empty translations: {empty}")

    def test_template_inlines_the_catalogue(self):
        template = (ASSETS / "template.html").read_text(encoding="utf-8")
        self.assertIn("{{I18N_JS}}", template)
        self.assertLess(
            template.index("{{I18N_JS}}"), template.index("{{APP_JS}}"),
            "the catalogue must load before the app that reads it",
        )


if __name__ == "__main__":
    sys.exit(0 if unittest.main(exit=False).result.wasSuccessful() else 1)
