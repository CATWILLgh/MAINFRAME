#!/usr/bin/env python3
"""Guard the keyboard and naming semantics of Observatory's custom controls."""

import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parent.parent
APP = (ROOT / "tools/hub_page_assets/app.js").read_text(encoding="utf-8")


class HubPageAccessibility(unittest.TestCase):
    def test_custom_cards_are_keyboard_activated(self):
        self.assertIn('card.setAttribute("role", "button")', APP)
        self.assertIn('card.setAttribute("tabindex", "0")', APP)
        self.assertIn("activateWithKeyboard(card, openCard)", APP)

    def test_resolvable_chips_are_native_buttons(self):
        self.assertIn('el(resolvable ? "button" : "span"', APP)
        self.assertIn('{ type: "button", class: "chip link" }', APP)

    def test_graph_nodes_are_named_keyboard_controls(self):
        self.assertIn('role: "button", tabindex: "0", "aria-label": n.label', APP)
        self.assertIn("activateWithKeyboard(g, () => openDetail(n.layer, n.id))", APP)

    def test_tab_panels_are_named_by_their_tabs(self):
        self.assertIn('const tabId = "tab-" + v.id', APP)
        self.assertIn('role: "tab", id: tabId', APP)
        self.assertIn('"aria-labelledby": tabId', APP)


if __name__ == "__main__":
    sys.exit(0 if unittest.main(exit=False).result.wasSuccessful() else 1)
