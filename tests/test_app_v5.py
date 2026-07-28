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
    compile_structured_query,
    determine_storage_location,
    execute_smarts_query,
    filter_sample_inventory,
    get_chemical_classification,
    load_sample_inventory,
    reset_add_workflow,
    route_natural_language_query,
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

    def test_structured_query_uses_bound_plan(self) -> None:
        frame = load_sample_inventory()
        plan = compile_structured_query("How much ethanol is left?", frame)
        self.assertEqual(plan["route"], "structured")
        self.assertEqual(plan["results"]["Chemical name"].tolist(), ["Ethanol"])
        self.assertIn("?", plan["query_code"])
        self.assertNotIn("ethanol", plan["query_code"].lower())
        malicious = compile_structured_query(
            "ethanol'; DROP TABLE inventory; --",
            frame,
        )
        self.assertNotIn("DROP TABLE", malicious["query_code"])

    def test_unknown_query_returns_no_inventory(self) -> None:
        frame = load_sample_inventory()
        plan = route_natural_language_query("What should I synthesize tomorrow?", frame)
        self.assertEqual(plan["route"], "unsupported")
        self.assertTrue(plan["results"].empty)

    def test_chemical_query_runs_structure_match_then_inventory_join(self) -> None:
        frame = load_sample_inventory()
        plan = route_natural_language_query(
            "Do we have a chiral phosphine ligand for asymmetric reduction?",
            frame,
        )
        self.assertEqual(plan["route"], "chemical")
        self.assertEqual(
            plan["results"]["Chemical name"].tolist(),
            ["(R)-BINAP", "(S)-SEGPHOS"],
        )
        self.assertTrue((plan["results"]["Quantity"] > 0).all())
        self.assertIn("Match evidence", plan["results"].columns)

    def test_chemical_concept_examples(self) -> None:
        frame = load_sample_inventory()
        expected = {
            "Which protic solvents are on hand?": ["Ethanol", "Methanol"],
            "Find a nitrile reagent": ["Acetonitrile"],
            "Show Lewis acids": ["Titanium tetrachloride"],
            "Find organometallic reagents": ["n-Butyllithium"],
        }
        for query, names in expected.items():
            with self.subTest(query=query):
                plan = route_natural_language_query(query, frame)
                self.assertEqual(plan["results"]["Chemical name"].tolist(), names)

    def test_invalid_smarts_fails_closed(self) -> None:
        frame = load_sample_inventory()
        result, _, warning = execute_smarts_query(frame, ["[invalid"], [])
        self.assertTrue(result.empty)
        self.assertIn("failed validation", warning)

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
        harness_template = """
import streamlit as st
from app_v5 import get_sample_extraction_result, render_registration_workspace

for field, value in get_sample_extraction_result().items():
    st.session_state.setdefault(f"add_field_{{field}}", value)
st.session_state.setdefault("add_extraction_complete", True)
st.session_state["add_stage"] = "{stage}"
st.session_state.setdefault("add_order_scenario", "Unique match")
st.session_state.setdefault("add_storage_location", "Flammable Cabinet B")
render_registration_workspace()
"""
        for stage in ("Details", "Order", "Storage", "Review"):
            app = AppTest.from_string(
                harness_template.format(stage=stage)
            ).run(timeout=20)
            self.assertEqual(len(app.exception), 0, stage)

    def test_main_workspace_navigation_renders_one_view_at_a_time(self) -> None:
        app = AppTest.from_file("app.py").run(timeout=20)
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(app.segmented_control[0].key, "primary_view")
        self.assertEqual(app.segmented_control[0].value, "Reagent intake")
        self.assertEqual(len(app.file_uploader), 1)
        self.assertEqual(len(app.text_area), 0)

        app.segmented_control[0].set_value("Inventory search")
        app.run(timeout=20)
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.file_uploader), 0)
        query_mode = next(
            control
            for control in app.segmented_control
            if control.key == "query_mode"
        )
        query_mode.set_value("Natural-language query")
        app.run(timeout=20)
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.text_area), 1)

    def test_chemical_query_interface_renders_verified_results(self) -> None:
        harness = """
from app_v5 import load_sample_inventory, render_natural_language_query
render_natural_language_query(load_sample_inventory())
"""
        app = AppTest.from_string(harness).run(timeout=20)
        self.assertEqual(len(app.exception), 0)
        app.text_area[0].set_value(
            "Do we have a chiral phosphine ligand for asymmetric reduction?"
        )
        next(
            button
            for button in app.button
            if button.label == "Run verified search"
        ).click()
        app.run(timeout=20)
        self.assertEqual(len(app.exception), 0)
        self.assertIn("2 verified on-hand match", app.success[0].value)

    def test_modern_streamlit_style_hooks_are_present(self) -> None:
        source = Path("app_v5.py").read_text(encoding="utf-8")
        self.assertIn('button[data-testid="stBaseButton-primary"]', source)
        self.assertIn('div[data-testid="stButtonGroup"]', source)
        self.assertIn(".st-key-primary_view", source)
        self.assertIn("@media (prefers-reduced-motion: reduce)", source)
        self.assertNotIn('st.tabs(["Add Reagent", "Query Inventory"])', source)
        config = Path(".streamlit/config.toml").read_text(encoding="utf-8")
        self.assertIn('base = "light"', config)


if __name__ == "__main__":
    unittest.main()
