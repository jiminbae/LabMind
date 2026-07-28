from __future__ import annotations

import unittest
import ast
from pathlib import Path

from streamlit.testing.v1 import AppTest

from app_v5 import (
    ADD_STATE_KEYS,
    can_confirm_registration,
    clear_state_keys,
    confirm_sample_registration,
    determine_storage_location,
    filter_sample_inventory,
    get_chemical_classification,
    load_sample_inventory,
    reset_add_workflow,
    synchronize_classification_state,
    uploaded_file_signature,
    validate_cas_number,
)


class AppV5HelpersTest(unittest.TestCase):
    def test_inventory_loads(self) -> None:
        frame = load_sample_inventory()
        self.assertGreaterEqual(len(frame), 10)
        self.assertIn("Chemical name", frame.columns)
        self.assertIn("Expiry state", frame.columns)

    def test_basic_filtering(self) -> None:
        frame = load_sample_inventory()
        result = filter_sample_inventory(
            frame,
            search_text="ethanol",
            manufacturer="Sigma-Aldrich",
        )
        self.assertEqual(result["Chemical name"].tolist(), ["Ethanol"])

    def test_file_signature_uses_contents(self) -> None:
        first = uploaded_file_signature(b"same-name-first-content")
        second = uploaded_file_signature(b"same-name-second-content")
        self.assertNotEqual(first, second)
        self.assertEqual(first, uploaded_file_signature(b"same-name-first-content"))

    def test_clear_state_keys_preserves_unrelated_values(self) -> None:
        state = {
            "add_extraction_complete": True,
            "add_confirmation": {"record_id": "LAB-1"},
            "unrelated": "keep",
        }
        clear_state_keys(state)
        self.assertEqual(state, {"unrelated": "keep"})

    def test_reset_clears_workflow_and_rotates_uploader(self) -> None:
        state = {key: "value" for key in ADD_STATE_KEYS}
        state["add_upload_nonce"] = 2
        state["unrelated"] = "keep"
        reset_add_workflow(state)
        self.assertEqual(state["add_upload_nonce"], 3)
        self.assertEqual(state["unrelated"], "keep")
        self.assertTrue(ADD_STATE_KEYS.isdisjoint(state))

    def test_confirmation_requires_review_and_extraction(self) -> None:
        self.assertFalse(can_confirm_registration(False, True))
        self.assertFalse(can_confirm_registration(True, False))
        self.assertTrue(can_confirm_registration(True, True))
        with self.assertRaises(ValueError):
            confirm_sample_registration({}, reviewed=False)
        result = confirm_sample_registration({"name": "Ethanol"}, reviewed=True)
        self.assertEqual(result["payload"]["name"], "Ethanol")

    def test_cas_check_digit_validation(self) -> None:
        self.assertTrue(validate_cas_number("64-17-5"))
        self.assertTrue(validate_cas_number("7732-18-5"))
        self.assertFalse(validate_cas_number("64-17-6"))
        self.assertFalse(validate_cas_number("not-a-cas"))

    def test_classification_cache_returns_multi_label_copy(self) -> None:
        first = get_chemical_classification("7550-45-0")
        second = get_chemical_classification("7550-45-0")
        self.assertIn("Lewis acid", first["labels"])
        self.assertIn("Moisture reactive", first["labels"])
        first["labels"].append("Changed")
        self.assertNotIn("Changed", second["labels"])
        unknown = get_chemical_classification("123-45-6")
        self.assertEqual(unknown["labels"], [])
        self.assertEqual(unknown["cache_status"], "Review required")

    def test_storage_rules_fail_closed(self) -> None:
        self.assertEqual(
            determine_storage_location(["Flammable"])["location"],
            "Flammable Cabinet B",
        )
        self.assertEqual(
            determine_storage_location(["Corrosive"])["location"],
            "Corrosives Cabinet",
        )
        self.assertEqual(
            determine_storage_location(["Refrigerated"])["location"],
            "Refrigerated Storage",
        )
        for constraints in (
            [],
            ["Water reactive"],
            ["Locked storage"],
            ["Corrosive", "Flammable"],
            ["Unsupported constraint"],
        ):
            self.assertEqual(
                determine_storage_location(list(constraints))["location"],
                "Manual Review Required",
            )

    def test_classification_state_refreshes_when_cas_changes(self) -> None:
        state = {"add_field_cas_number": "64-17-5"}
        synchronize_classification_state(state)
        self.assertIn("Flammable liquid", state["add_chemical_labels"])
        self.assertEqual(state["add_storage_location"], "Flammable Cabinet B")
        state["add_field_cas_number"] = "109-72-8"
        synchronize_classification_state(state)
        self.assertIn("Organometallic", state["add_chemical_labels"])
        self.assertEqual(state["add_storage_location"], "Manual Review Required")

    def test_no_backend_module_is_imported(self) -> None:
        source = Path("app_v5.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        forbidden = {
            "backend",
            "db_utils",
            "order_matcher",
            "vision_extract",
            "rule_engine",
            "nl_query",
            "rdkit_matcher",
        }
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        self.assertTrue(forbidden.isdisjoint(imported))

    def test_registration_stages_render_without_errors(self) -> None:
        harness = """
import streamlit as st
from app_v5 import get_sample_extraction_result, render_registration_workspace

for field, value in get_sample_extraction_result().items():
    st.session_state.setdefault(f"add_field_{field}", value)
st.session_state.setdefault("add_extraction_complete", True)
st.session_state.setdefault("add_stage", "Details")
st.session_state.setdefault("add_order_scenario", "Unique match")
st.session_state.setdefault("add_storage_location", "Flammable Cabinet B")
render_registration_workspace()
"""
        app = AppTest.from_string(harness).run(timeout=20)
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(app.segmented_control[0].value, "Details")

        for stage in ("Order", "Storage", "Review"):
            app.segmented_control[0].set_value(stage)
            app.run(timeout=20)
            self.assertEqual(len(app.exception), 0, stage)

    def test_modern_streamlit_style_hooks_are_present(self) -> None:
        source = Path("app_v5.py").read_text(encoding="utf-8")
        self.assertIn('button[data-testid="stBaseButton-primary"]', source)
        self.assertIn('button[data-testid="stTab"]', source)
        self.assertIn('div[data-testid="stButtonGroup"]', source)
        config = Path(".streamlit/config.toml").read_text(encoding="utf-8")
        self.assertIn('base = "light"', config)


if __name__ == "__main__":
    unittest.main()
