import json
from pathlib import Path
import unittest

from installer.core import Conflict
from installer.shared import inventory
from installer.state import component_keys, reconcile_state, set_component


ROOT = Path(__file__).resolve().parents[1]


class AdaptationStateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = inventory(ROOT)
        cls.keys = set(component_keys(cls.source))

    def test_delivery_is_established_by_current_adapter_outcomes(self):
        component = ("skills", "mainframe-research")
        prior = json.loads(json.dumps(self.source))
        prior["schema_version"] = 1
        prior.pop("delivery_values")
        prior.pop("verification_values")
        prior["status_values"] = ["pending", "installed", "unsupported"]
        prior["components"][component[0]][component[1]] = {
            "source": "skills/mainframe-research",
            "status": "installed",
            "note": "Current surface loaded the exact skill.",
        }
        state = reconcile_state(
            self.source, prior, {"product": "fixture"}, unchanged=True,
            delivered={component},
        )
        row = state["components"][component[0]][component[1]]
        self.assertEqual(row["delivery"], "installed")
        self.assertEqual(row["verification"], "passed")
        self.assertNotIn("reason", row)

        reset = reconcile_state(
            self.source, prior, {"product": "fixture"}, unchanged=True,
        )
        row = reset["components"][component[0]][component[1]]
        self.assertEqual(row["delivery"], "pending")
        self.assertEqual(row["verification"], "pending")

    def test_old_pending_notes_are_shared_once_and_unsupported_omits_verification(self):
        prior = json.loads(json.dumps(self.source))
        prior["schema_version"] = 1
        prior.pop("delivery_values")
        prior.pop("verification_values")
        prior["status_values"] = ["pending", "installed", "unsupported"]
        repeated = "Reload this target and check discovery."
        for category, name in self.keys:
            prior["components"][category][name] = {
                "source": prior["components"][category][name]["source"],
                "status": "pending", "note": repeated,
            }
        unsupported = ("hooks", "mainframe-code-quality")
        prior["components"][unsupported[0]][unsupported[1]].update(
            status="unsupported", note="The required completion advisory is unavailable."
        )
        state = reconcile_state(
            self.source, prior, {"product": "fixture"}, unchanged=True,
        )
        self.assertEqual(state["next_actions"], [repeated])
        rows = [row for group in state["components"].values() for row in group.values()]
        self.assertFalse(any(row.get("next_action") == repeated for row in rows))
        row = state["components"][unsupported[0]][unsupported[1]]
        self.assertEqual(row["delivery"], "unsupported")
        self.assertNotIn("verification", row)
        self.assertEqual(row["reason"], "The required completion advisory is unavailable.")

    def test_reason_is_reserved_for_unsupported_limitations(self):
        state = json.loads(json.dumps(self.source))
        component = ("skills", "mainframe-research")
        with self.assertRaisesRegex(Conflict, "Only an unsupported component can have a reason"):
            set_component(
                state, component, delivery="installed", verification="passed",
                reason="Successful discovery evidence.",
            )


if __name__ == "__main__":
    unittest.main()
