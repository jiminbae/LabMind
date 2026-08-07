from __future__ import annotations

import os
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

import app_v5
from app_v5 import (
    ADD_STATE_KEYS,
    Chem,
    can_confirm_registration,
    clear_state_keys,
    compile_structured_query,
    confirm_sample_registration,
    determine_storage_location,
    execute_smarts_query,
    filter_sample_inventory,
    get_chemical_classification,
    get_sample_extraction_result,
    load_sample_inventory,
    reset_add_workflow,
    route_natural_language_query,
    synchronize_classification_state,
    uploaded_file_signature,
    validate_cas_number,
)
from backend.db_utils import list_reagents
from backend.query_translation_service import QueryTranslationResult


SINGLE_PIXEL_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010804000000b51c0c02"
    "0000000b4944415478da6364f80f00010501012718e3660000000049454e44ae426082"
)


class AppV5HelpersTest(unittest.TestCase):
    """Exercise the Streamlit helpers against an isolated real SQLite database."""

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "inventory.db"
        # A few UI helpers resolve the database internally, so isolate those
        # calls as well as the explicit db_path integration calls below.
        self.database_environment = patch.dict(
            os.environ,
            {"LABMIND_DB_PATH": str(self.database_path)},
            clear=False,
        )
        self.database_environment.start()

    def tearDown(self) -> None:
        self.database_environment.stop()
        self.temporary_directory.cleanup()

    def database_argument(self) -> str:
        return str(self.database_path)

    def test_streamlit_provider_environment_reads_render_environment(self) -> None:
        with patch.dict(
            os.environ,
            {
                "LABMIND_VISION_MODE": "live",
                "LABMIND_PROVIDER": "gemini",
                "GEMINI_API_KEY": "render-secret",
            },
            clear=False,
        ):
            environment = app_v5.streamlit_provider_environment()

        self.assertEqual(environment["LABMIND_VISION_MODE"], "live")
        self.assertEqual(environment["LABMIND_PROVIDER"], "gemini")
        self.assertEqual(environment["GEMINI_API_KEY"], "render-secret")

    def reagent_payload(
        self,
        *,
        chemical_name: str = "Ethanol",
        cas_number: str = "64-17-5",
        manufacturer: str = "Sigma-Aldrich",
        batch_number: str = "LOT-ETH-01",
        specification: str = "ACS grade",
        quantity: int = 2,
        volume_ml: float = 500,
        expiry_date: str | None = None,
        labels: list[str] | None = None,
        constraints: list[str] | None = None,
        receipt_key: str | None = None,
    ) -> dict[str, object]:
        labels = labels or [
            "Flammable liquid",
            "Protic solvent",
            "Organic compound",
        ]
        constraints = constraints or ["Flammable", "Keep away from oxidizers"]
        decision = determine_storage_location(constraints)
        return {
            "chemical_name": chemical_name,
            "cas_number": cas_number,
            "specification": specification,
            "batch_number": batch_number,
            "manufacturer": manufacturer,
            "expiry_date": expiry_date
            or (date.today() + timedelta(days=365)).isoformat(),
            "quantity": quantity,
            "volume_ml": volume_ml,
            "confidence": 0.91,
            "extraction_source": "Manual test entry",
            "extraction_rationale": "Reviewed test receipt.",
            "pending_order": "Not linked",
            "match_score": None,
            "receipt_key": receipt_key or f"test:{cas_number}:{batch_number}",
            "image_signature": "test-image-signature",
            "chemical_labels": labels,
            "storage_constraints": constraints,
            "classification_confidence": 0.94,
            "classification_source": "Reviewed test profile",
            "classification_rationale": "Verified against the test profile.",
            "storage_location": decision["location"],
            "storage_rule": decision["rule"],
            "storage_reviewed": True,
        }

    def register(self, payload: dict[str, object]) -> dict[str, object]:
        return confirm_sample_registration(
            payload,
            reviewed=True,
            db_path=self.database_argument(),
        )

    def load_inventory(self):
        return load_sample_inventory(db_path=self.database_argument())

    def test_empty_database_has_a_stable_inventory_contract(self) -> None:
        frame = self.load_inventory()

        self.assertTrue(frame.empty)
        self.assertEqual(
            list(frame.columns),
            [
                "Record ID",
                "Chemical name",
                "CAS number",
                "Manufacturer",
                "Batch number",
                "Specification",
                "Quantity",
                "Volume (mL)",
                "Expiry date",
                "Storage location",
                "SMILES",
                "Chemical labels",
                "Storage constraints",
                "Expiry state",
                "Status",
                "Order reference",
                "Classification source",
            ],
        )

    def test_reviewed_registration_is_visible_in_inventory_and_idempotent(self) -> None:
        payload = self.reagent_payload()

        first = self.register(payload)
        retry = self.register(payload)
        frame = self.load_inventory()
        stored = list_reagents(self.database_argument())

        self.assertEqual(first["record_id"], "LAB-0001")
        self.assertTrue(first["created"])
        self.assertEqual(retry["record_id"], first["record_id"])
        self.assertFalse(retry["created"])
        self.assertEqual(len(frame), 1)
        self.assertEqual(frame.loc[0, "Record ID"], "LAB-0001")
        self.assertEqual(frame.loc[0, "Chemical name"], "Ethanol")
        self.assertEqual(frame.loc[0, "CAS number"], "64-17-5")
        self.assertEqual(frame.loc[0, "Status"], "Available")
        self.assertEqual(len(stored), 1)
        self.assertFalse(stored[0]["manual_review"])
        self.assertEqual(stored[0]["extraction_confidence"], 0.91)
        self.assertEqual(stored[0]["classification_source"], "Reviewed test profile")

    def test_unreviewed_registration_does_not_create_a_database(self) -> None:
        with self.assertRaises(ValueError):
            confirm_sample_registration(
                self.reagent_payload(),
                reviewed=False,
                db_path=self.database_argument(),
            )

        self.assertFalse(self.database_path.exists())

    def test_basic_filtering_reads_real_registered_records(self) -> None:
        self.register(self.reagent_payload())
        self.register(
            self.reagent_payload(
                chemical_name="Methanol",
                cas_number="67-56-1",
                batch_number="LOT-MEOH-01",
                manufacturer="Fisher Scientific",
                quantity=1,
                volume_ml=40,
                receipt_key="test:67-56-1:LOT-MEOH-01",
            )
        )
        frame = self.load_inventory()

        result = filter_sample_inventory(
            frame,
            search_text="ethanol",
            manufacturer="Sigma-Aldrich",
            minimum_quantity=1,
            minimum_volume_ml=100,
        )

        self.assertEqual(result["Chemical name"].tolist(), ["Ethanol"])
        self.assertEqual(result["Quantity"].tolist(), [2])
        self.assertEqual(result["Volume (mL)"].tolist(), [500.0])

    def test_inventory_view_renders_records_without_expiry_dates(self) -> None:
        self.register(self.reagent_payload(expiry_date=None))
        app = AppTest.from_file("app.py").run(timeout=20)
        app.segmented_control[0].set_value("Inventory search")
        app.run(timeout=20)

        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.dataframe), 1)
        self.assertEqual(
            app.dataframe[0].value["Chemical name"].tolist(),
            ["Ethanol"],
        )

    def test_natural_query_renders_records_without_expiry_dates(self) -> None:
        self.register(self.reagent_payload(expiry_date=None))
        app = AppTest.from_string(
            "from app_v5 import render_query_tab\nrender_query_tab()"
        ).run(timeout=20)
        app.segmented_control[0].set_value("Natural-language query")
        app.run(timeout=20)
        app.text_area[0].set_value("How much ethanol is left?")
        next(
            button
            for button in app.button
            if button.label == "Verify question against inventory"
        ).click()
        app.run(timeout=20)

        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.dataframe), 1)
        self.assertEqual(
            app.dataframe[0].value["Chemical name"].tolist(),
            ["Ethanol"],
        )
        self.assertEqual(len(app.code), 0)

    def test_structured_query_runs_against_loaded_inventory_only(self) -> None:
        self.register(self.reagent_payload())
        self.register(
            self.reagent_payload(
                chemical_name="Acetonitrile",
                cas_number="75-05-8",
                batch_number="LOT-ACN-01",
                manufacturer="Fisher Scientific",
                quantity=5,
                receipt_key="test:75-05-8:LOT-ACN-01",
            )
        )
        frame = self.load_inventory()

        plan = compile_structured_query("How much ethanol is left?", frame)
        malicious = compile_structured_query(
            "ethanol'; DROP TABLE inventory; --",
            frame,
        )

        self.assertEqual(plan["route"], "structured")
        self.assertEqual(plan["results"]["Chemical name"].tolist(), ["Ethanol"])
        self.assertIn("?", plan["query_code"])
        self.assertNotIn("ethanol", plan["query_code"].lower())
        self.assertNotIn("DROP TABLE", malicious["query_code"])

    def test_named_inventory_item_wins_over_chemical_concept_translation(self) -> None:
        self.register(
            self.reagent_payload(
                chemical_name="(R)-BINAP",
                cas_number="76189-55-4",
                batch_number="LOT-BINAP-NAMED",
                quantity=0,
                expiry_date=(date.today() - timedelta(days=1)).isoformat(),
                labels=[],
                receipt_key="test:76189-55-4:LOT-BINAP-NAMED",
            )
        )
        frame = self.load_inventory()

        by_short_name = route_natural_language_query(
            "Do we have BINAP, a chiral ligand?",
            frame,
        )
        by_cas = route_natural_language_query(
            "Is CAS 76189-55-4 currently in inventory?",
            frame,
        )

        self.assertEqual(by_short_name["route"], "structured")
        self.assertEqual(by_cas["route"], "structured")
        self.assertEqual(
            by_short_name["results"]["Chemical name"].tolist(),
            ["(R)-BINAP"],
        )
        self.assertEqual(
            by_cas["results"]["Chemical name"].tolist(),
            ["(R)-BINAP"],
        )
        self.assertEqual(by_short_name["results"]["Quantity"].tolist(), [0])
        self.assertEqual(by_short_name["results"]["Status"].tolist(), ["Expired"])

    def test_smarts_query_joins_only_to_available_nonexpired_records(self) -> None:
        if Chem is None:
            self.skipTest("RDKit is not installed in this runtime.")
        self.register(
            self.reagent_payload(
                chemical_name="(R)-BINAP",
                cas_number="76189-55-4",
                batch_number="LOT-BINAP-01",
                manufacturer="Strem",
                quantity=2,
                labels=[
                    "Chiral ligand",
                    "Phosphine ligand",
                    "Organophosphorus compound",
                ],
                constraints=["Ambient temperature", "Keep away from oxidizers"],
                receipt_key="test:76189-55-4:LOT-BINAP-01",
            )
        )
        self.register(
            self.reagent_payload(
                chemical_name="(S)-SEGPHOS",
                cas_number="210169-54-3",
                batch_number="LOT-SEGPHOS-01",
                manufacturer="TCI",
                quantity=0,
                expiry_date=(date.today() - timedelta(days=1)).isoformat(),
                labels=[
                    "Chiral ligand",
                    "Phosphine ligand",
                    "Organophosphorus compound",
                ],
                constraints=["Ambient temperature", "Keep away from oxidizers"],
                receipt_key="test:210169-54-3:LOT-SEGPHOS-01",
            )
        )
        frame = self.load_inventory()

        plan = route_natural_language_query(
            "Do we have a chiral phosphine ligand for asymmetric reduction?",
            frame,
        )
        invalid, _, warning = execute_smarts_query(frame, ["[invalid"], [])

        self.assertEqual(plan["route"], "chemical")
        self.assertEqual(plan["results"]["Chemical name"].tolist(), ["(R)-BINAP"])
        self.assertTrue((plan["results"]["Quantity"] > 0).all())
        self.assertTrue((plan["results"]["Status"] != "Expired").all())
        self.assertIn("Match evidence", plan["results"].columns)
        self.assertTrue(invalid.empty)
        self.assertIn("failed validation", warning)

    def test_unfamiliar_chemical_query_reaches_live_translator(self) -> None:
        if Chem is None:
            self.skipTest("RDKit is not installed in this runtime.")
        self.register(self.reagent_payload())
        frame = self.load_inventory()
        translation = QueryTranslationResult(
            status="success",
            translation={
                "concept": "Alcohol-containing reagent",
                "patterns": ["[O]"],
                "required_labels": [],
                "explanation": "Contains oxygen.",
            },
            message="A chemistry search plan was proposed.",
        )

        with patch("app_v5.translate_chemical_question", return_value=translation) as call:
            plan = route_natural_language_query(
                "Do we have an alcohol-containing reagent?",
                frame,
                provider_environment={
                    "LABMIND_VISION_MODE": "live",
                    "GEMINI_API_KEY": "test-key",
                },
            )

        call.assert_called_once()
        self.assertEqual(plan["route"], "chemical")
        self.assertEqual(plan["results"]["Chemical name"].tolist(), ["Ethanol"])

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

    def test_confirmation_requires_review_and_a_valid_persisted_payload(self) -> None:
        self.assertFalse(can_confirm_registration(False, True))
        self.assertFalse(can_confirm_registration(True, False))
        self.assertTrue(can_confirm_registration(True, True))
        with self.assertRaises(ValueError):
            confirm_sample_registration({}, reviewed=False, db_path=self.database_argument())

        result = self.register(self.reagent_payload())
        self.assertEqual(result["payload"]["chemical_name"], "Ethanol")
        self.assertEqual(result["record_id"], "LAB-0001")

    def test_cas_check_digit_validation(self) -> None:
        self.assertTrue(validate_cas_number("64-17-5"))
        self.assertTrue(validate_cas_number("7732-18-5"))
        self.assertFalse(validate_cas_number("64-17-6"))
        self.assertFalse(validate_cas_number("not-a-cas"))

    def test_classification_profiles_are_copied_and_unknowns_fail_closed(self) -> None:
        first = get_chemical_classification("7550-45-0")
        second = get_chemical_classification("7550-45-0")
        self.assertIn("Lewis acid", first["labels"])
        self.assertIn("Moisture reactive", first["labels"])
        first["labels"].append("Changed")
        self.assertNotIn("Changed", second["labels"])
        unknown = get_chemical_classification("123-45-6")
        self.assertEqual(unknown["labels"], [])
        self.assertEqual(unknown["cache_status"], "Manual classification required")

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

    def test_unknown_query_returns_no_inventory(self) -> None:
        self.register(self.reagent_payload())
        frame = self.load_inventory()
        plan = route_natural_language_query("What should I synthesize tomorrow?", frame)
        self.assertEqual(plan["route"], "unsupported")
        self.assertTrue(plan["results"].empty)

    def test_registration_stages_render_blank_manual_fields_without_errors(self) -> None:
        harness_template = """
import streamlit as st
from app_v5 import get_sample_extraction_result, render_registration_workspace

for field, value in get_sample_extraction_result().items():
    st.session_state.setdefault(f"add_field_{{field}}", value)
st.session_state.setdefault("add_extraction_complete", True)
st.session_state.setdefault("add_receipt_key", "test-render")
st.session_state.setdefault("add_register_without_order", True)
st.session_state["add_stage"] = "{stage}"
render_registration_workspace()
"""
        for stage in ("Details", "Order", "Storage", "Review"):
            app = AppTest.from_string(harness_template.format(stage=stage)).run(timeout=20)
            self.assertEqual(len(app.exception), 0, stage)

    def test_classification_callback_updates_rendered_multiselects_without_error(self) -> None:
        app = AppTest.from_string(
            """
import streamlit as st
import app_v5
from backend.classification_service import ClassificationResult

st.session_state.setdefault("add_extraction_complete", True)
st.session_state.setdefault("add_field_chemical_name", "Formaldehyde")
st.session_state.setdefault("add_field_cas_number", "50-00-0")
app_v5.classify_cas_with_gemini = lambda *args, **kwargs: ClassificationResult(
    status="success",
    classification={
        "cas_number": "50-00-0",
        "labels": ["Reducing agent"],
        "constraints": ["Keep away from oxidizers"],
        "confidence": 0.88,
        "cache_status": "Gemini chemical classification",
        "rationale": "Test classification.",
    },
    message="AI classification is ready for review.",
)
app_v5.render_storage_step()
"""
        ).run(timeout=20)
        self.assertEqual(len(app.exception), 0)

        next(
            widget
            for widget in app.multiselect
            if widget.key == "add_chemical_labels"
        ).set_value(["Organic compound"])
        next(
            widget
            for widget in app.multiselect
            if widget.key == "add_storage_constraints"
        ).set_value(["Ambient temperature"])
        app.run(timeout=20)
        next(
            button
            for button in app.button
            if button.label == "Generate AI chemistry profile"
        ).click()
        app.run(timeout=20)

        self.assertEqual(len(app.exception), 0)
        state = app.session_state.filtered_state
        self.assertEqual(
            state["add_chemical_labels"],
            ["Organic compound", "Reducing agent"],
        )
        self.assertEqual(
            state["add_storage_constraints"],
            ["Ambient temperature", "Keep away from oxidizers"],
        )

    def test_manual_extraction_fields_survive_stage_navigation_without_sample_data(self) -> None:
        app = AppTest.from_file("app.py").run(timeout=20)
        app.file_uploader[0].upload(
            "label.png",
            SINGLE_PIXEL_PNG,
            "image/png",
        )
        app.run(timeout=20)
        next(
            button for button in app.button if button.label == "Read label with Gemini"
        ).click()
        app.run(timeout=20)
        next(
            button for button in app.button if button.label == "Continue to order"
        ).click()
        app.run(timeout=20)

        state = app.session_state.filtered_state
        self.assertEqual(state["add_stage"], "Order")
        self.assertEqual(state["add_field_chemical_name"], "")
        self.assertEqual(state["add_field_cas_number"], "")
        self.assertEqual(state["add_field_quantity"], 0)
        self.assertEqual(state["add_field_volume_ml"], 0.0)
        self.assertEqual(state["add_extraction_notice"]["status"], "manual")
        self.assertIn("manually", state["add_extraction_notice"]["message"].lower())

    def test_intake_uses_integer_container_quantity_and_separate_ml_volume(self) -> None:
        app = AppTest.from_string(
            """
import streamlit as st
from app_v5 import get_sample_extraction_result, render_extraction_step

for field, value in get_sample_extraction_result().items():
    st.session_state[f"add_field_{field}"] = value
st.session_state["add_extraction_complete"] = True
render_extraction_step()
"""
        ).run(timeout=20)

        self.assertEqual(len(app.exception), 0)
        quantity = next(
            widget
            for widget in app.number_input
            if widget.label == "Quantity (containers)"
        )
        volume = next(
            widget
            for widget in app.number_input
            if widget.label == "Volume per container (mL)"
        )
        self.assertIsInstance(quantity.value, int)
        self.assertEqual(quantity.value, 0)
        self.assertIsInstance(volume.value, float)
        self.assertEqual(volume.value, 0.0)

    def test_partial_reextraction_preserves_manual_and_nonvision_values(self) -> None:
        app = AppTest.from_string(
            """
from datetime import date
import streamlit as st
import app_v5
from backend.vision_service import LabelExtractionResult

st.session_state["add_field_cas_number"] = "64-17-5"
st.session_state["add_field_manufacturer"] = "Reviewed manufacturer"
st.session_state["add_field_quantity"] = 25
st.session_state["add_field_volume_ml"] = 500.0
st.session_state["add_field_expiry_date"] = date(2027, 1, 2)

original_extract_label_fields = app_v5.extract_label_fields
app_v5.extract_label_fields = lambda *args, **kwargs: LabelExtractionResult(
    status="partial",
    fields={
        "chemical_name": "Ethanol",
        "cas_number": "",
        "specification": "",
        "batch_number": "LOT-NEW",
        "manufacturer": "",
        "confidence": 81,
    },
    message="Some label fields were extracted.",
    provider="gemini",
)
try:
    app_v5.initialize_extraction_state(b"image", "label.png")
finally:
    app_v5.extract_label_fields = original_extract_label_fields
st.write("complete")
"""
        ).run(timeout=20)

        self.assertEqual(len(app.exception), 0)
        state = app.session_state.filtered_state
        self.assertEqual(state["add_field_chemical_name"], "Ethanol")
        self.assertEqual(state["add_field_cas_number"], "64-17-5")
        self.assertEqual(state["add_field_manufacturer"], "Reviewed manufacturer")
        self.assertEqual(state["add_field_batch_number"], "LOT-NEW")
        self.assertEqual(state["add_field_quantity"], 25)
        self.assertEqual(state["add_field_volume_ml"], 500.0)
        self.assertEqual(state["add_field_expiry_date"], date(2027, 1, 2))

    def test_partial_extraction_notice_is_a_warning(self) -> None:
        app = AppTest.from_string(
            """
import streamlit as st
from app_v5 import get_sample_extraction_result, render_extraction_step

for field, value in get_sample_extraction_result().items():
    st.session_state[f"add_field_{field}"] = value
st.session_state["add_extraction_complete"] = True
st.session_state["add_extraction_notice"] = {
    "status": "partial",
    "message": "Some label fields were extracted.",
}
render_extraction_step()
"""
        ).run(timeout=20)

        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.warning), 1)
        self.assertEqual(len(app.success), 0)
        self.assertIn("Some label fields", app.warning[0].value)

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

    def test_chemical_query_interface_renders_verified_real_database_results(self) -> None:
        if Chem is None:
            self.skipTest("RDKit is not installed in this runtime.")
        for chemical_name, cas_number, batch_number in (
            ("(R)-BINAP", "76189-55-4", "LOT-BINAP-UI"),
            ("(S)-SEGPHOS", "210169-54-3", "LOT-SEGPHOS-UI"),
        ):
            self.register(
                self.reagent_payload(
                    chemical_name=chemical_name,
                    cas_number=cas_number,
                    batch_number=batch_number,
                    manufacturer="Strem",
                    quantity=2,
                    labels=[
                        "Chiral ligand",
                        "Phosphine ligand",
                        "Organophosphorus compound",
                    ],
                    constraints=["Ambient temperature", "Keep away from oxidizers"],
                    receipt_key=f"test:{cas_number}:{batch_number}",
                )
            )
        harness = f"""
from app_v5 import load_sample_inventory, render_natural_language_query
render_natural_language_query(load_sample_inventory(db_path={self.database_argument()!r}))
"""
        app = AppTest.from_string(harness).run(timeout=20)
        self.assertEqual(len(app.exception), 0)
        app.text_area[0].set_value(
            "Do we have a chiral phosphine ligand for asymmetric reduction?"
        )
        next(
            button
            for button in app.button
            if button.label == "Verify question against inventory"
        ).click()
        app.run(timeout=20)
        self.assertEqual(len(app.exception), 0)
        self.assertIn("2 verified on-hand match", app.success[0].value)

    def test_modern_streamlit_style_hooks_are_present(self) -> None:
        source = Path("app_v5.py").read_text(encoding="utf-8")
        self.assertIn('button[data-testid="stBaseButton-primary"]', source)
        self.assertIn('div[data-testid="stButtonGroup"]', source)
        self.assertIn('div[data-testid="stSpinner"]', source)
        self.assertIn(".st-key-primary_view", source)
        self.assertIn("@media (prefers-reduced-motion: reduce)", source)
        self.assertNotIn('st.tabs(["Add Reagent", "Query Inventory"])', source)
        config = Path(".streamlit/config.toml").read_text(encoding="utf-8")
        self.assertIn('base = "light"', config)

    def test_natural_query_omits_suggested_questions_and_workflow_trace(self) -> None:
        source = Path("app_v5.py").read_text(encoding="utf-8")
        self.assertNotIn("Suggested questions", source)
        self.assertNotIn("st.pills(", source)
        self.assertNotIn('class="query-trace"', source)

    def test_slow_actions_have_specific_loading_feedback(self) -> None:
        source = Path("app_v5.py").read_text(encoding="utf-8")
        self.assertIn("Reading the reagent label with Gemini…", source)
        self.assertIn(
            "Generating chemical functions and storage constraints with Gemini…",
            source,
        )
        self.assertIn("Interpreting the question and verifying inventory…", source)
        self.assertIn("Saving the reviewed reagent record…", source)


if __name__ == "__main__":
    unittest.main()
