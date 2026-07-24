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
    filter_sample_inventory,
    load_sample_inventory,
    reset_add_workflow,
    uploaded_file_signature,
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
