from __future__ import annotations

import hashlib
import html
import json
import os
import re
from io import BytesIO
from datetime import date, datetime, timedelta
from typing import Any, MutableMapping
from uuid import uuid4

import pandas as pd
import streamlit as st

from backend.app_service import (
    load_inventory_frame,
    register_reagent_payload,
)
from backend.chemistry_catalog import catalog_profile
from backend.classification_cache import get_cas_classification
from backend.classification_service import classify_cas_with_gemini
from backend.order_matching import (
    import_pending_orders,
    match_pending_orders,
    select_unique_order_match,
)
from backend.provider_config import PROVIDER_ENV_NAMES
from backend.query_translation_service import translate_chemical_question
from backend.safety_rules import determine_storage_location
from backend.vision_service import extract_label_fields

try:
    from rdkit import Chem
except ImportError:  # The UI fails closed until the chemistry runtime is installed.
    Chem = None


ADD_STATE_KEYS = {
    "add_file_signature",
    "add_upload_time",
    "add_receipt_key",
    "add_extraction_notice",
    "add_stage",
    "add_extraction_complete",
    "add_extraction_source",
    "add_extraction_rationale",
    "add_confirmation",
    "add_order_scenario",
    "add_selected_order",
    "add_order_match_score",
    "add_register_without_order",
    "add_storage_location",
    "add_classification_cas",
    "add_chemical_labels",
    "add_storage_constraints",
    "add_classification_confidence",
    "add_classification_source",
    "add_classification_rationale",
    "add_classification_notice",
    "add_classification_requested",
    "add_storage_rule",
    "add_storage_decision_signature",
    "add_manual_storage_reviewed",
    "add_reviewed",
    "add_field_chemical_name",
    "add_field_cas_number",
    "add_field_specification",
    "add_field_batch_number",
    "add_field_manufacturer",
    "add_field_expiry_date",
    "add_field_quantity",
    "add_field_unit",
    "add_field_confidence",
}

STORAGE_OPTIONS = [
    "General Shelf A",
    "General Shelf B",
    "Flammable Cabinet A",
    "Flammable Cabinet B",
    "Corrosives Cabinet",
    "Refrigerated Storage",
    "Freezer Storage",
    "Manual Review Required",
]

CHEMICAL_LABEL_OPTIONS = [
    "BrÃ¸nsted acid",
    "Chiral ligand",
    "Flammable liquid",
    "Inorganic compound",
    "Lewis acid",
    "Moisture reactive",
    "Organic compound",
    "Organometallic",
    "Organophosphorus compound",
    "Phosphine ligand",
    "Protic solvent",
    "Pyrophoric",
    "Reducing agent",
]

STORAGE_CONSTRAINT_OPTIONS = [
    "Ambient temperature",
    "Corrosive",
    "Flammable",
    "Keep away from acids",
    "Keep away from oxidizers",
    "Locked storage",
    "Refrigerated",
    "Segregate from bases",
    "Water reactive",
]


def apply_theme() -> None:
    st.markdown(
        """
        <style>
        :root {
            --canvas: #f3f6f8;
            --surface: rgba(255, 255, 255, 0.96);
            --surface-strong: #ffffff;
            --ink: #14202b;
            --secondary: #506170;
            --tertiary: #697986;
            --line: #d8e1e8;
            --line-strong: #b9c6cf;
            --navy: #17324d;
            --accent: #1957d2;
            --accent-hover: #1247b5;
            --accent-soft: #eaf0ff;
            --teal: #087a70;
            --teal-soft: #e7f5f2;
            --green: #147a4c;
            --amber: #9b5a00;
            --red: #c81e3a;
            --shadow: 0 12px 32px rgba(20, 32, 43, 0.055);
            --radius-card: 18px;
            --radius-control: 11px;
            --space-1: 8px;
            --space-2: 12px;
            --space-3: 16px;
            --space-4: 24px;
            --space-5: 32px;
            --space-6: 48px;
            --space-7: 64px;
        }

        html, body, [class*="css"] {
            font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display",
                "SF Pro Text", "Helvetica Neue", Arial, sans-serif;
            -webkit-font-smoothing: antialiased;
        }

        .stApp {
            background:
                radial-gradient(circle at 12% -80px, #ffffff 0, rgba(255, 255, 255, 0) 440px),
                radial-gradient(circle at 94% 8%, rgba(25, 87, 210, 0.055), transparent 330px),
                var(--canvas);
            color: var(--ink);
        }

        div.block-container {
            max-width: 1120px;
            padding: .75rem 2rem 4rem;
        }

        section[data-testid="stMain"] {
            overflow-x: hidden;
        }

        header[data-testid="stHeader"] {
            background: transparent;
        }

        #MainMenu,
        footer,
        div[data-testid="stToolbar"],
        div[data-testid="stDecoration"],
        div[data-testid="stStatusWidget"] {
            display: none !important;
        }

        h1, h2, h3 {
            color: var(--ink);
            letter-spacing: -0.015em;
        }

        .topbar {
            align-items: center;
            border-bottom: 1px solid var(--line);
            display: flex;
            justify-content: space-between;
            min-height: 60px;
            padding: 0 2px 14px;
        }

        .brand {
            align-items: center;
            display: flex;
            gap: 11px;
        }

        .brand-mark {
            align-items: center;
            background: var(--navy);
            border-radius: 8px;
            color: #fff;
            display: inline-flex;
            font-size: 13px;
            font-weight: 760;
            height: 38px;
            justify-content: center;
            letter-spacing: -0.02em;
            width: 38px;
        }

        .brand-name {
            color: var(--ink);
            font-size: 18px;
            font-weight: 760;
            line-height: 1.1;
        }

        .brand-subtitle {
            color: var(--secondary);
            font-size: 12px;
            margin-top: 3px;
        }

        .topbar-note {
            align-items: center;
            background: var(--teal-soft);
            border: 1px solid rgba(8, 122, 112, 0.18);
            border-radius: 999px;
            color: #075f58;
            display: flex;
            font-size: 12px;
            font-weight: 680;
            gap: 7px;
            padding: 7px 10px;
        }

        .topbar-note-dot {
            background: var(--teal);
            border-radius: 999px;
            box-shadow: 0 0 0 4px rgba(8, 122, 112, 0.10);
            height: 7px;
            width: 7px;
        }

        .hero {
            align-items: center;
            display: grid;
            gap: clamp(30px, 5vw, 72px);
            grid-template-columns: minmax(0, 1.1fr) minmax(330px, .9fr);
            padding: 34px 0 26px;
            text-align: left;
        }

        .hero-kicker {
            align-items: center;
            color: var(--teal);
            display: inline-flex;
            font-size: 12px;
            font-weight: 760;
            gap: 7px;
            letter-spacing: .08em;
            margin-bottom: 12px;
            text-transform: uppercase;
        }

        .hero-kicker::before {
            background: var(--teal);
            border-radius: 50%;
            box-shadow: 0 0 0 4px rgba(8, 122, 112, .10);
            content: "";
            height: 7px;
            width: 7px;
        }

        .hero-title {
            color: var(--ink);
            font-size: clamp(42px, 4.8vw, 58px);
            font-weight: 760;
            letter-spacing: -0.052em;
            line-height: 1.01;
            margin: 0;
            max-width: 680px;
        }

        .hero-title span {
            color: var(--navy);
        }

        .hero-copy {
            color: var(--secondary);
            font-size: 16px;
            letter-spacing: -0.01em;
            line-height: 1.6;
            margin: 16px 0 0;
            max-width: 620px;
        }

        .capability-rail {
            align-items: stretch;
            background: var(--surface-strong);
            border: 1px solid var(--line);
            border-radius: var(--radius-card);
            box-shadow: var(--shadow);
            display: grid;
            gap: 0;
            grid-template-columns: 1fr;
            margin: 0;
            overflow: hidden;
            padding: 6px;
            width: 100%;
        }

        .capability {
            align-items: center;
            display: grid;
            gap: 2px 10px;
            grid-template-columns: 32px 1fr;
            padding: 14px 13px;
            text-align: left;
        }

        .capability + .capability {
            border-left: 0;
            border-top: 1px solid var(--line);
        }

        .capability > span {
            align-items: center;
            background: var(--accent-soft);
            border-radius: 9px;
            color: var(--accent);
            display: flex;
            font-size: 11px;
            font-weight: 760;
            grid-row: 1 / 3;
            height: 32px;
            justify-content: center;
            letter-spacing: 0.03em;
            padding: 0;
            width: 32px;
        }

        .capability strong {
            color: var(--ink);
            font-size: 14px;
            font-weight: 700;
        }

        .capability small {
            color: var(--secondary);
            font-size: 12px;
            line-height: 1.4;
        }

        .section-header {
            margin: 0;
            padding-top: 2px;
        }

        .section-eyebrow {
            color: var(--teal);
            font-size: 11px;
            font-weight: 760;
            letter-spacing: 0.1em;
            margin-bottom: 7px;
            text-transform: uppercase;
        }

        .section-title {
            color: var(--ink);
            font-size: clamp(28px, 2.7vw, 36px);
            font-weight: 740;
            letter-spacing: -0.04em;
            line-height: 1.1;
            margin: 0;
        }

        .section-copy {
            color: var(--secondary);
            font-size: 15px;
            line-height: 1.55;
            margin: 8px 0 0;
            max-width: 720px;
        }

        .stepper {
            background: transparent;
            display: grid;
            gap: 0;
            grid-template-columns: repeat(5, 1fr);
            margin: 6px 0 var(--space-2);
        }

        .step {
            align-items: center;
            background: transparent;
            border: 0;
            border-radius: 0;
            color: var(--tertiary);
            display: flex;
            flex-direction: column;
            font-size: 12px;
            gap: 6px;
            overflow: visible;
            padding: 0 4px;
            position: relative;
            text-align: center;
            white-space: normal;
        }

        .step::before {
            background: var(--line);
            content: "";
            height: 1px;
            left: 0;
            position: absolute;
            right: 0;
            top: 12px;
            z-index: 0;
        }

        .step:first-child::before {
            left: 50%;
        }

        .step:last-child::before {
            right: 50%;
        }

        .step strong {
            align-items: center;
            background: var(--canvas);
            border: 1px solid var(--line-strong);
            border-radius: 50%;
            color: var(--secondary);
            display: flex;
            font-size: 10px;
            font-weight: 760;
            height: 25px;
            justify-content: center;
            margin: 0;
            position: relative;
            width: 25px;
            z-index: 1;
        }

        .step.active {
            background: transparent;
            color: var(--ink);
            font-weight: 700;
        }

        .step.active strong {
            background: var(--accent);
            border-color: var(--accent);
            box-shadow: 0 0 0 4px rgba(25, 87, 210, .11);
            color: #fff;
        }

        .step.complete {
            background: transparent;
            color: var(--navy);
            font-weight: 650;
        }

        .step.complete strong {
            background: var(--navy);
            border-color: var(--navy);
            color: #fff;
        }

        div[data-testid="stTabs"] [data-baseweb="tab-list"] {
            background: rgba(118, 118, 128, 0.11);
            border: 1px solid rgba(0, 0, 0, 0.06);
            border-radius: 13px;
            gap: 0;
            padding: 4px;
            width: fit-content;
        }

        div[data-testid="stTabs"] button[data-baseweb="tab"] {
            border-radius: 9px;
            color: var(--secondary);
            font-size: 14px;
            font-weight: 590;
            height: 38px;
            padding: 0 18px;
        }

        div[data-testid="stTabs"] button[aria-selected="true"] {
            background: #fff;
            box-shadow: 0 1px 4px rgba(0, 0, 0, 0.12);
            color: var(--ink);
        }

        div[data-testid="stTabs"] button p,
        div[data-testid="stTabs"] button span {
            color: inherit !important;
        }

        div[data-testid="stTabs"] [data-baseweb="tab-highlight"] {
            display: none;
        }

        div[data-testid="stTabs"] [data-baseweb="tab-border"] {
            display: none;
        }

        div[data-testid="stTabs"] [role="tablist"] {
            background: rgba(118, 118, 128, 0.11);
            border: 1px solid rgba(0, 0, 0, 0.06);
            border-radius: 13px;
            gap: 0;
            padding: 4px;
            width: fit-content;
        }

        div[data-testid="stTabs"] [role="tablist"]::after,
        div[data-testid="stTabs"] .react-aria-SelectionIndicator {
            display: none !important;
        }

        div[data-testid="stTabs"] button[data-testid="stTab"] {
            border-radius: 9px;
            color: var(--secondary) !important;
            font-size: 14px;
            font-weight: 590;
            height: 38px;
            padding: 0 18px;
        }

        div[data-testid="stTabs"] button[data-testid="stTab"][data-selected],
        div[data-testid="stTabs"] button[data-testid="stTab"][aria-selected="true"] {
            background: #fff;
            box-shadow: 0 1px 4px rgba(0, 0, 0, 0.12);
            color: var(--ink) !important;
        }

        .st-key-upload_panel,
        .st-key-review_placeholder,
        .st-key-registration_panel,
        .st-key-query_panel {
            background: var(--surface);
            border: 1px solid var(--line);
 ßowæÚ$z{-®éÜj×7B#àÐ¢ÆF—cãÇ7ããÂ÷7ããÇ7G&öæsä6†VÖ–6ÂæÖSÂ÷7G&öæsãÂöF—càÐ¢ÆF—cãÇ7ãã#Â÷7ããÇ7G&öæsä42çVÖ&W#Â÷7G&öæsãÂöF—càÐ¢ÆF—cãÇ7ãã3Â÷7ããÇ7G&öæså7V6–f–6F–öãÂ÷7G&öæsãÂöF—càÐ¢ÆF—cãÇ7ããCÂ÷7ããÇ7G&öæsä&F6‚÷"Æ÷CÂ÷7G&öæsãÂöF—càÐ¢ÆF—cãÇ7ããSÂ÷7ããÇ7G&öæsäÖçVf7GW&W#Â÷7G&öæsãÂöF—càÐ¢ÂöF—càÐ¢"""ÀÐ¢Vç6fUöÆÆ÷uö‡FÖÃÕG'VRÀÐ¢Ð¢&WGW&àÐ¢v—F‚7Bæ6öçF–æW"†&÷&FW#ÕG'VRÂ¶W“Ò'&Vv—7G&F–öå÷æVÂ"“ Ð¢&VæFW%÷&Vv—7G&F–öå÷v÷&·76R‚Ð Ð Ð¦FVb&VæFW%ö–çfVçF÷'•öÖWG&–72†g&ÖS¢BäFFg&ÖR’ÓâæöæS Ð¢ÖçVf7GW&W%ö6÷VçBÒ–çB†g&ÖU²$ÖçVf7GW&W"%ÒæçVæ—VR‚’’–bæ÷Bg&ÖRæV×G’VÇ6R Ð¢GFVçF–öåö6÷VçBÒ–çB€Ð¢g&ÖU²$W‡—'’7FFR%Òæ—6–â…²$W‡—&–ær6ööâ"Â$W‡—&VB%Ò’ç7VÒ‚Ð¢Ð¢7BæÖ&¶F÷vâ€Ð¢b"" Ð¢ÆF—b6Æ73Ò&ÖWG&–2×&÷r#àÐ¢ÆF—b6Æ73Ò&ÖWG&–2Ö6&B#àÐ¢ÆF—b6Æ73Ò&ÖWG&–2×fÇVR#ç¶ÆVâ†g&ÖR—ÓÂöF—càÐ¢ÆF—b6Æ73Ò&ÖWG&–2ÖÆ&VÂ#äÖF6†VB&V6÷&G3ÂöF—càÐ¢ÂöF—càÐ¢ÆF—b6Æ73Ò&ÖWG&–2Ö6&B#àÐ¢ÆF—b6Æ73Ò&ÖWG&–2×fÇVR#ç¶ÖçVf7GW&W%ö6÷VçGÓÂöF—càÐ¢ÆF—b6Æ73Ò&ÖWG&–2ÖÆ&VÂ#äÖçVf7GW&W'3ÂöF—càÐ¢ÂöF—càÐ¢ÆF—b6Æ73Ò&ÖWG&–2Ö6&B#àÐ¢ÆF—b6Æ73Ò&ÖWG&–2×fÇVR#ç¶GFVçF–öåö6÷VçGÓÂöF—càÐ¢ÆF—b6Æ73Ò&ÖWG&–2ÖÆ&VÂ#äW‡—'’GFVçF–öãÂöF—càÐ¢ÂöF—càÐ¢ÂöF—càÐ¢"""ÀÐ¢Vç6fUöÆÆ÷uö‡FÖÃÕG'VRÀÐ¢Ð Ð Ð¦FVb6WE÷&–Ö'•÷f–Wr‡f–Ws¢7G"’ÓâæöæS ¢7Bç6W76–öå÷7FFU²'&–Ö'•÷f–Wr%ÒÒf–Wp  ¦FVb&VæFW%ö–çfVçF÷'•÷&W7VÇG2€¢g&ÖS¢BäFFg&ÖRÀ¢¢À¢–çfVçF÷'•ö—5öV×G“¢&ööÂÒfÇ6RÀ¢’ÓâæöæS ¢–bg&ÖRæV×G“ ¢–b–çfVçF÷'•ö—5öV×G“ ¢F—FÆRÒ$'V–ÆB–÷W"f—'7BG'W7FVB–çfVçF÷'’&V6÷&B ¢6÷’Ò€¢$6ö×ÆWFRfW&–f–VB&VvVçB–çF¶RÂF†Vâ&WGW&â†W&RFò6V&6‚F†R ¢'&Wf–WvVB&VvVçBâ ¢¢VÇ6S ¢F—FÆRÒ$æò&Wf–WvVB–çfVçF÷'’&V6÷&G2ÖF6‚ ¢6÷’Ò$'&öFVâF†R&WVW7B÷"6ÆV"öæR÷"Ö÷&R6öç7G&–çG2ÂF†VâfW&–g’v–ââ ¢7BæÖ&¶F÷vâ€¢b"" ¢ÆF—b6Æ73Ò&V×G’×7FFR"&öÆSÒ'7FGW2#à¢ÆF—b6Æ73Ò&V×G’×7FFRÖÖ&²#ãÂöF—cà¢ÆF—b6Æ73Ò&V×G’×7FFR×F—FÆR#ç¶W66VB‡F—FÆR—ÓÂöF—cà¢ÆF—b6Æ73Ò&V×G’×7FFRÖ6÷’#ç¶W66VB†6÷’—ÓÂöF—cà¢ÂöF—cà¢"""À¢Vç6fUöÆÆ÷uö‡FÖÃÕG'VRÀ¢¢–b–çfVçF÷'•ö—5öV×G“ ¢7Bæ'WGFöâ€¢$&Vv–â&VvVçB–çF¶R"À¢¶W“Ò&V×G•ö–çfVçF÷'•÷Fõö–çF¶R"À¢öåö6Æ–6³×6WE÷&–Ö'•÷f–WrÀ¢&w3Ò‚%&VvVçB–çF¶R"Â’À¢¢&WGW&à ¢&VæFW%ö–çfVçF÷'•öÖWG&–72†g&ÖR¢F—7Æ•ög&ÖRÒg&ÖRæ6÷’‚¢F—7Æ•ög&ÖU²$W‡—'’FFR%ÒÒBçFõöFFWF–ÖR€¢F—7Æ•ög&ÖU²$W‡—'’FFR%ÒÀ¢W'&÷'3Ò&6öW&6R"À¢¢F—7Æ•ö6öÇVÖç2Ò°Ð¢%&V6÷&B”B"ÀÐ¢$6†VÖ–6ÂæÖR"ÀÐ¢$42çVÖ&W""ÀÐ¢$ÖçVf7GW&W""ÀÐ¢%VçF—G’"ÀÐ¢%Væ—B"ÀÐ¢%7FGW2"ÀÐ¢$W‡—'’FFR"ÀÐ¢%7F÷&vRÆö6F–öâ"ÀÐ¢ÐÐ¢–b$ÖF6‚Wf–FVæ6R"–âF—7Æ•ög&ÖRæ6öÇVÖç3 Ð¢F—7Æ•ö6öÇVÖç2æW‡FVæB…²$6†VÖ–6ÂÆ&VÇ2"Â%4Ô”ÄU2"Â$ÖF6‚Wf–FVæ6R%ÒÐ¢F—7Æ•ö6öÇVÖç2Ò°Ð¢6öÇVÖâf÷"6öÇVÖâ–âF—7Æ•ö6öÇVÖç2–b6öÇVÖâ–âF—7Æ•ög&ÖRæ6öÇVÖç0Ð¢ÐÐ¢7BæFFg&ÖR€Ð¢F—7Æ•ög&ÖU¶F—7Æ•ö6öÇVÖç5ÒÀÐ¢v–GFƒÒ'7G&WF6‚"ÀÐ¢†–FUö–æFWƒÕG'VRÀÐ¢6öÇVÖåö6öæf–s×°Ð¢$W‡—'’FFR#¢7Bæ6öÇVÖåö6öæf–räFFT6öÇVÖâ‚$W‡—'’FFR"Âf÷&ÖCÒ%•••’ÔÔÒÔDB"’ÀÐ¢%VçF—G’#¢7Bæ6öÇVÖåö6öæf–räçVÖ&W$6öÇVÖâ‚%VçF—G’"Âf÷&ÖCÒ"VB"’ÀÐ¢ÒÀÐ¢Ð¢7BæF÷væÆöEö'WGFöâ€Ð¢$W‡÷'BfW&–f–VB&W7VÇG2255b"À¢FFÖg&ÖRçFõö77b†–æFWƒÔfÇ6R’æVæ6öFR‚'WFbÓ‚"’ÀÐ¢f–ÆUöæÖSÒ&Æ&Ö–æBÖ–çfVçF÷'’×&W7VÇG2æ77b"ÀÐ¢Ö–ÖSÒ'FW‡Bö77b"ÀÐ¢v–GFƒÒ'7G&WF6‚"ÀÐ¢Ð Ð¢6†'Eö6†ö–6RÒ7Bç6VÆV7F&÷‚€Ð¢%f—7VÆ—¦R"ÀÐ¢°Ð¢%&V6÷&G2'’7F÷&vRÆö6F–öâ"ÀÐ¢%&V6÷&G2'’ÖçVf7GW&W""ÀÐ¢$W‡—'’7FGW2F—7G&–'WF–öâ"ÀÐ¢ÒÀÐ¢¶W“Ò'VW'•ö6†'B"ÀÐ¢Ð¢–b6†'Eö6†ö–6RÓÒ%&V6÷&G2'’7F÷&vRÆö6F–öâ# Ð¢6†'EöFFÒg&ÖRæw&÷W'’‚%7F÷&vRÆö6F–öâ"’ç6—¦R‚’ç&VæÖR‚%&V6÷&G2"Ð¢VÆ–b6†'Eö6†ö–6RÓÒ%&V6÷&G2'’ÖçVf7GW&W"# Ð¢6†'EöFFÒg&ÖRæw&÷W'’‚$ÖçVf7GW&W""’ç6—¦R‚’ç&VæÖR‚%&V6÷&G2"Ð¢VÇ6S Ð¢6†'EöFFÒg&ÖRæw&÷W'’‚$W‡—'’7FFR"’ç6—¦R‚’ç&VæÖR‚%&V6÷&G2"Ð¢7Bæ&%ö6†'B†6†'EöFFÂ6öÆ÷#Ò"3sS2"Ð Ð Ð¦FVb6ÆV%÷VW'•÷7FFR‚’ÓâæöæS ¢¶W—2Ò°Ð¢'VW'•÷6V&6‚"ÀÐ¢'VW'•öÖçVf7GW&W""ÀÐ¢'VW'•÷7F÷&vR"ÀÐ¢'VW'•öW‡—'’"ÀÐ¢'VW'•öÖ–æ–×VÒ"ÀÐ¢'VW'•÷&W7VÇG2"ÀÐ¢'VW'•öæGW&Å÷FW‡B"À¢'VW'•öæGW&Å÷Æâ"À¢'VW'•öæGW&Å÷Æå÷VW7F–öâ"À¢ÐÐ¢6ÆV%÷7FFUö¶W—2‡7Bç6W76–öå÷7FFRÂg&÷¦Vç6WB†¶W—2’Ð Ð Ð¦FVb&VæFW%ö&6–5÷VW'’†g&ÖS¢BäFFg&ÖR’ÓâBäFFg&ÖS Ð¢6V&6‚Ò7BçFW‡Eö–çWB€¢%6V&6‚&Wf–WvVB–çfVçF÷'’"À¢Æ6V†öÆFW#Ò$6†VÖ–6ÂÂ42çVÖ&W"Â&F6‚Â÷"&V6÷&B”B"ÀÐ¢¶W“Ò'VW'•÷6V&6‚"ÀÐ¢Ð¢f–ÇFW%ö6öÇ2Ò7Bæ6öÇVÖç2ƒBÐ¢v—F‚f–ÇFW%ö6öÇ5³Ó Ð¢ÖçVf7GW&W"Ò7Bç6VÆV7F&÷‚€Ð¢$ÖçVf7GW&W""ÀÐ¢²$ÆÂÖçVf7GW&W'2%Ò²6÷'FVB†g&ÖU²$ÖçVf7GW&W"%ÒçVæ—VR‚’çFöÆ—7B‚’’ÀÐ¢¶W“Ò'VW'•öÖçVf7GW&W""ÀÐ¢Ð¢v—F‚f–ÇFW%ö6öÇ5³Ó Ð¢7F÷&vRÒ7Bç6VÆV7F&÷‚€Ð¢%7F÷&vR"ÀÐ¢²$ÆÂÆö6F–öç2%Ò²6÷'FVB†g&ÖU²%7F÷&vRÆö6F–öâ%ÒçVæ—VR‚’çFöÆ—7B‚’’ÀÐ¢¶W“Ò'VW'•÷7F÷&vR"ÀÐ¢Ð¢v—F‚f–ÇFW%ö6öÇ5³%Ó Ð¢W‡—'’Ò7Bç6VÆV7F&÷‚€Ð¢$W‡—'’7FFR"ÀÐ¢²$ÆÂW‡—'’7FFW2"Â$7W'&VçB"Â$W‡—&–ær6ööâ"Â$W‡—&VB%ÒÀÐ¢¶W“Ò'VW'•öW‡—'’"ÀÐ¢Ð¢v—F‚f–ÇFW%ö6öÇ5³5Ó Ð¢Ö–æ–×VÒÒ7BæçVÖ&W%ö–çWB€Ð¢$Ö–æ–×VÒVçF—G’"ÀÐ¢Ö–å÷fÇVSÓÀÐ¢7FWÓÀÐ¢¶W“Ò'VW'•öÖ–æ–×VÒ"ÀÐ¢Ð¢6V&6…ö6öÂÂ6ÆV%ö6öÂÒ7Bæ6öÇVÖç2…³ÂÒÐ¢v—F‚6V&6…ö6öÃ Ð¢6V&6…ö6Æ–6¶VBÒ7Bæ'WGFöâ€¢$Ç’–çfVçF÷'’f–ÇFW'2"À¢G—SÒ'&–Ö'’"ÀÐ¢v–GFƒÒ'7G&WF6‚"ÀÐ¢¶W“Ò''Våö&6–5÷VW'’"ÀÐ¢Ð¢v—F‚6ÆV%ö6öÃ ¢7Bæ'WGFöâ€¢$6ÆV"f–ÇFW'2"À¢v–GFƒÒ'7G&WF6‚"À¢¶W“Ò&6ÆV%ö&6–5÷VW'’"À¢öåö6Æ–6³Ö6ÆV%÷VW'•÷7FFRÀ¢F—6&ÆVCÖæ÷B&ööÂ€¢6V&6‚ç7G&—‚¢÷"ÖçVf7GW&W"Ò$ÆÂÖçVf7GW&W'2 ¢÷"7F÷&vRÒ$ÆÂÆö6F–öç2 ¢÷"W‡—'’Ò$ÆÂW‡—'’7FFW2 ¢÷"Ö–æ–×VÒâ ¢’À¢¢–b6V&6…ö6Æ–6¶VB÷"'VW'•÷&W7VÇG2"æ÷B–â7Bç6W76–öå÷7FFS ¢v—F‚7Bç7–ææW"‚$6†V6¶–ærF†RÆöFVB–çfVçF÷'’&V6÷&G>(
b"“ ¢7Bç6W76–öå÷7FFU²'VW'•÷&W7VÇG2%ÒÒf–ÇFW%÷6×ÆUö–çfVçF÷'’€¢g&ÖRÀ¢6V&6…÷FW‡C×6V&6‚À¢ÖçVf7GW&W#ÖÖçVf7GW&W"À¢7F÷&vUöÆö6F–öã×7F÷&vRÀ¢W‡—'•÷7FFSÖW‡—'’À¢Ö–æ–×VÕ÷VçF—G“Ö–çB†Ö–æ–×VÒ’À¢¢&WGW&â7Bç6W76–öå÷7FFU²'VW'•÷&W7VÇG2%ÐÐ Ð Ð¦FVb6WEöæGW&Å÷VW'•öW†×ÆR‡VW7F–öã¢7G"’ÓâæöæS Ð¢7Bç6W76–öå÷7FFU²'VW'•öæGW&Å÷FW‡B%ÒÒVW7F–öàÐ¢7Bç6W76–öå÷7FFRç÷‚'VW'•öæGW&Å÷Æâ"ÂæöæRÐ Ð Ð¦FVbÇ•öæGW&Å÷VW'•öW†×ÆR†W†×ÆW3¢F–7E·7G"Â7G%Ò’ÓâæöæS Ð¢6VÆV7F–öâÒ7Bç6W76–öå÷7FFRævWB‚'VW'•öW†×ÆUö6†ö–6R"Ð¢–b6VÆV7F–öâ–âW†×ÆW3 Ð¢6WEöæGW&Å÷VW'•öW†×ÆR†W†×ÆW5·6VÆV7F–öåÒÐ Ð Ð¦FVb&VæFW%öæGW&ÅöÆæwVvU÷VW'’†g&ÖS¢BäFFg&ÖR’ÓâBäFFg&ÖS ¢VW'•÷FW‡BÒ7BçFW‡Eö&V€¢$6²6†VÖ—7G'’÷"–çfVçF÷'’VW7F–öâ"À¢Æ6V†öÆFW#Ò€Ð¢%G'’(	ÄFòvR†fR6†—&Â†÷7†–æRÆ–væBf÷"7–ÖÖWG&–2&VGV7F–öãþ(	Ò Ð¢’ÀÐ¢†V–v‡CÓÀÐ¢¶W“Ò'VW'•öæGW&Å÷FW‡B"ÀÐ¢Ð¢W†×ÆW2Ò°Ð¢$6†—&ÂÆ–væG2#¢€Ð¢$FòvR†fR6†—&Â†÷7†–æRÆ–væBf÷"7–ÖÖWG&–2&VGV7F–öãò Ð¢’ÀÐ¢%&÷F–26öÇfVçG2#¢%v†–6‚&÷F–26öÇfVçG2&R7W'&VçFÇ’öâ†æCò"ÀÐ¢$W‡—'’6†V6²#¢%6†÷r&VvVçG2W‡—&–ærv—F†–â3F—2â"ÀÐ¢ÐÐ¢7Bç–ÆÇ2€Ð¢%7VvvW7FVBVW7F–öç2"ÀÐ¢Æ—7B†W†×ÆW2’ÀÐ¢¶W“Ò'VW'•öW†×ÆUö6†ö–6R"ÀÐ¢v–GFƒÒ'7G&WF6‚"ÀÐ¢Æ&VÅ÷f—6–&–Æ—G“Ò&6öÆÆ6VB"ÀÐ¢öåö6†ævSÖÇ•öæGW&Å÷VW'•öW†×ÆRÀÐ¢&w3Ò†W†×ÆW2Â’ÀÐ¢Ð¢–b7Bæ'WGFöâ€¢%fW&–g’VW7F–öâv–ç7B–çfVçF÷'’"À¢G—SÒ'&–Ö'’"À¢v–GFƒÒ'7G&WF6‚"À¢¶W“Ò''VåöæGW&Å÷VW'’"À¢F—6&ÆVCÖæ÷BVW'•÷FW‡Bç7G&—‚’À¢“ ¢7V&Ö—GFVE÷VW7F–öâÒ7Bç6W76–öå÷7FFRævWB‚'VW'•öæGW&Å÷FW‡B"Â""’ç7G&—‚¢v—F‚7Bç7–ææW"€¢$–çFW'&WF–ærF†RVW7F–öâæBfW&–g––ær–çfVçF÷'ž(
b"À¢6†÷u÷F–ÖSÕG'VRÀ¢“ ¢7Bç6W76–öå÷7FFU²'VW'•öæGW&Å÷Æâ%ÒÒ&÷WFUöæGW&ÅöÆæwVvU÷VW'’€¢7V&Ö—GFVE÷VW7F–öâÀ¢g&ÖRÀ¢&÷f–FW%öVçf—&öæÖVçC×7G&VÖÆ—E÷&÷f–FW%öVçf—&öæÖVçB‚’À¢¢7Bç6W76–öå÷7FFU²'VW'•öæGW&Å÷Æå÷VW7F–öâ%ÒÒ7V&Ö—GFVE÷VW7F–öà Ð¢v—F‚7BæW‡æFW"‚$†÷rÆ$Ö–æBfW&–f–W2âç7vW""“ ¢7BæÖ&¶F÷vâ€Ð¢"" Ð¢ÆF—b6Æ73Ò'fW&–f–6F–öâÖ&÷VæF'’#àÐ¢Ç7G&öæsä’–çFW'&WG2–çFVçBâÆ"–çfVçF÷'’FWFW&Ö–æW2f–Æ&–Æ—G’ãÂ÷7G&öæsà¢Ç7ãàÐ¢7G'V7GW&VBVW7F–öç2&V6öÖR&÷VæBf–ÇFW'2â6†VÖ—7G'’VW7F–öç2&V6öÖPÐ¢fÆ–FFVB4Ô%E2Â'VâF‡&÷Vv‚$D¶—BÂF†Vâ¦ö–â&6²FòöâÖ†æB&V6÷&G2àÐ¢Â÷7ãàÐ¢ÂöF—càÐ¢"""ÀÐ¢Vç6fUöÆÆ÷uö‡FÖÃÕG'VRÀÐ¢Ð Ð¢ÆâÒ7Bç6W76–öå÷7FFRævWB‚'VW'•öæGW&Å÷Æâ"¢ÆåöÖF6†W5÷VW7F–öâÒ€¢7Bç6W76–öå÷7FFRævWB‚'VW'•öæGW&Å÷Æå÷VW7F–öâ"’ÓÒVW'•÷FW‡Bç7G&—‚¢¢–bæ÷BÆâ÷"æ÷BÆåöÖF6†W5÷VW7F–öã ¢7BæÖ&¶F÷vâ€Ð¢sÆF—b6Æ73Ò'VW'’×&VG’#ä6²Æ$Ö–æBVW7F–öâFò6VRF†RfW&–f–VBW†V7WF–öâF‚æBÖF6†–æröâÖ†æB&V6÷&G2ãÂöF—cârÀ¢Vç6fUöÆÆ÷uö‡FÖÃÕG'VRÀÐ¢Ð¢&WGW&âV×G•ö–çfVçF÷'•÷&W7VÇB†g&ÖRÐ Ð¢7BæÖ&¶F÷vâ€Ð¢b"" Ð¢ÆF—b6Æ73Ò&÷&FW"Ö6&B6VÆV7FVB#àÐ¢ÆF—b6Æ73Ò'VW'’×&÷WFR#ç¶W66VB‡Æå²'&÷WFUöÆ&VÂ%Ò—ÓÂöF—càÐ¢ÆF—b6Æ73Ò&÷&FW"ÖæÖR#ç¶W66VB‡Æå²&–çFW'&WFF–öâ%Ò—ÓÂöF—càÐ¢ÆF—b6Æ73Ò&÷&FW"ÖFWF–Â#àÐ¢¶W66VB‡ÆâævWB‚&W‡ÆæF–öâ"Â$âÆÆ÷vÆ—7FVBÆâ—2W†V7WFVBv–ç7BF†RÆöFVB–çfVçF÷'’â"’—ÐÐ¢ÂöF—càÐ¢ÂöF—càÐ¢"""ÀÐ¢Vç6fUöÆÆ÷uö‡FÖÃÕG'VRÀÐ¢Ð¢–bÆå²'&÷WFR%ÒÓÒ&6†VÖ–6Â# Ð¢G&6RÒ°Ð¢‚#+r–çFW'&WB"Â$6†VÖ–6Â6öæ6WB"’ÀÐ¢‚#"+rfÆ–FFR"Â%4Ô%E2GFW&â"’ÀÐ¢‚#2+rÖF6‚"Â%$D¶—B7G'V7GW&W2"’ÀÐ¢‚#B+rfW&–g’"Â$öâÖ†æB–çfVçF÷'’¦ö–â"’ÀÐ¢ÐÐ¢VÆ–bÆå²'&÷WFR%ÒÓÒ'7G'V7GW&VB# Ð¢G&6RÒ°Ð¢‚#+r–çFW'&WB"Â$–çfVçF÷'’–çFVçB"’ÀÐ¢‚#"+r6ö×–ÆR"Â$&÷fVB&V6÷&Bf–ÇFW""’ÀÐ¢‚#2+rÇ’"Â$ÆöFVB–çfVçF÷'’&V6÷&G2"’ÀÐ¢‚#B+r&WGW&â"Â%fW&–f–VB&V6÷&B7FFR"’ÀÐ¢ÐÐ¢VÇ6S Ð¢G&6RÒ°Ð¢‚#+r–ç7V7B"Â%VW7F–öâ&V6V—fVB"’ÀÐ¢‚#"+r7F÷6fVÇ’"Â$æò&÷fVBG&ç6ÆF–öâ"’ÀÐ¢ÐÐ¢G&6Uö‡FÖÂÒ""æ¦ö–â€Ð¢bsÆF—b6Æ73Ò'G&6R×7FW#ãÇ7G&öæsç¶W66VB‡F—FÆR—ÓÂ÷7G&öæsç¶W66VB†6÷’—ÓÂöF—câpÐ¢f÷"F—FÆRÂ6÷’–âG&6PÐ¢Ð¢7BæÖ&¶F÷vâ€Ð¢bsÆF—b6Æ73Ò'VW'’×G&6R#ç·G&6Uö‡FÖÇÓÂöF—cârÀÐ¢Vç6fUöÆÆ÷uö‡FÖÃÕG'VRÀÐ¢Ð¢–bÆå²'VW'•ö6öFR%Ó Ð¢7Bæ6öFR‡Æå²'VW'•ö6öFR%ÒÐ¢–bÆâævWB‚'&ÖWFW'2"“ Ð¢7Bæ6F–öâ€Ð¢$&÷VæB&ÖWFW'2ò&WV—&VBÆ&VÇ3¢ Ð¢²"+r"æ¦ö–â‡7G"‡fÇVR’f÷"fÇVR–âÆå²'&ÖWFW'2%ÒÐ¢Ð¢–bÆâævWB‚'v&æ–ær"“ Ð¢7Bçv&æ–ær‡Æå²'v&æ–ær%ÒÐ¢–bÆå²'&÷WFR%ÒÓÒ&6†VÖ–6Â"æBæ÷BÆâævWB‚'v&æ–ær"“ ¢ÖF6…ö6÷VçBÒÆVâ‡Æå²'&W7VÇG2%Ò¢6¶—VEö6÷VçBÒ–çB‡ÆâævWB‚'6¶—VB"Â’¢ÖF6…öÆ&VÂÒ&ÖF6‚"–bÖF6…ö6÷VçBÓÒVÇ6R&ÖF6†W2 ¢6¶—VEöÆ&VÂÒ'&V6÷&B"–b6¶—VEö6÷VçBÓÒVÇ6R'&V6÷&G2 ¢ÖW76vRÒ€¢b'¶ÖF6…ö6÷VçGÒfW&–f–VBöâÖ†æB¶ÖF6…öÆ&VÇÒ+r ¢b'·6¶—VEö6÷VçGÒ7G'V7GW&R·6¶—VEöÆ&VÇÒ6¶—VB ¢¢–bÖF6…ö6÷VçC ¢7Bç7V66W72†ÖW76vR¢VÇ6S ¢7BæÖ&¶F÷vâ€¢bsÆF—b6Æ73Ò'7FGW2ÖÆ–æRæWWG&Â"&öÆSÒ'7FGW2#âp¢bsÇ7â6Æ73Ò'7FGW2ÖF÷B#ãÂ÷7ãç¶W66VB†ÖW76vR—ÓÂöF—cârÀ¢Vç6fUöÆÆ÷uö‡FÖÃÕG'VRÀ¢¢&WGW&âÆå²'&W7VÇG2%ÐÐ Ð Ð¦FVb&VæFW%÷VW'•÷F"‚’ÓâæöæS Ð¢g&ÖRÒÆöE÷6×ÆUö–çfVçF÷'’‚Ð¢&VæFW%÷6V7F–öåö†VFW"€¢%fW&–f–VB–çfVçF÷'’6V&6‚"À¢%6V&6‚öæÇ’v†BF†RÆ"†2öâ†æB"À¢%W6R&V6—6Rf–ÇFW'2÷"6²6†VÖ—7G'’VW7F–öââWfW'’ç7vW"—26†V6¶VBv–ç7B&Wf–WvVB–çfVçF÷'’&V6÷&G2â"À¢Ð¢ÖöFRÒ7Bç6VvÖVçFVEö6öçG&öÂ€Ð¢%VW'’ÖöFR"ÀÐ¢²$&6–2f–ÇFW'2"Â$æGW&ÂÖÆæwVvRVW'’%ÒÀÐ¢¶W“Ò'VW'•öÖöFR"ÀÐ¢FVfVÇCÒ$&6–2f–ÇFW'2"ÀÐ¢&WV—&VCÕG'VRÀÐ¢v–GFƒÒ'7G&WF6‚"ÀÐ¢Æ&VÅ÷f—6–&–Æ—G“Ò&6öÆÆ6VB"ÀÐ¢Ð¢v—F‚7Bæ6öçF–æW"†&÷&FW#ÕG'VRÂ¶W“Ò'VW'•÷æVÂ"“ Ð¢–bÖöFRÓÒ$&6–2f–ÇFW'2# Ð¢&W7VÇG2Ò&VæFW%ö&6–5÷VW'’†g&ÖRÐ¢VÇ6S Ð¢&W7VÇG2Ò&VæFW%öæGW&ÅöÆæwVvU÷VW'’†g&ÖRÐ¢–bÖöFRÓÒ$&6–2f–ÇFW'2"÷"7Bç6W76–öå÷7FFRævWB‚'VW'•öæGW&Å÷Æâ"“ ¢&VæFW%ö–çfVçF÷'•÷&W7VÇG2‡&W7VÇG2Â–çfVçF÷'•ö—5öV×G“Ög&ÖRæV×G’¢7BæÖ&¶F÷vâ€Ð¢sÇ6Æ73Ò'V–WBÖæ÷FR#äÆ$Ö–æBÖ’G&ç6ÆFR–÷W"–çFVçBÂ'WB7G'V7GW&RÂVçF—G’Â7FGW2ÂæBW‡—'’Çv—26öÖRg&öÒÆöFVB–çfVçF÷'’&V6÷&G2ãÂ÷ârÀ¢Vç6fUöÆÆ÷uö‡FÖÃÕG'VRÀÐ¢Ð Ð Ð¦FVbÖ–â‚’ÓâæöæS Ð¢7Bç6WE÷vUö6öæf–r€¢vU÷F—FÆSÒ$Æ$Ö–æB(	BfW&–f–VB&VvVçB–çFVÆÆ–vVæ6R"À¢vUö–6öãÒ/	úz¢"À¢Æ–÷WCÒ'v–FR"ÀÐ¢–æ—F–Å÷6–FV&%÷7FFSÒ&6öÆÆ6VB"ÀÐ¢Ð¢Ç•÷F†VÖR‚Ð¢&VæFW%÷F÷&"‚Ð¢&VæFW%ö†W&ò‚Ð¢&–Ö'•÷f–WrÒ7Bç6VvÖVçFVEö6öçG&öÂ€Ð¢%v÷&·76R"ÀÐ¢²%&VvVçB–çF¶R"Â$–çfVçF÷'’6V&6‚%ÒÀÐ¢¶W“Ò'&–Ö'•÷f–Wr"ÀÐ¢FVfVÇCÒ%&VvVçB–çF¶R"ÀÐ¢&WV—&VCÕG'VRÀÐ¢v–GFƒÒ'7G&WF6‚"ÀÐ¢Æ&VÅ÷f—6–&–Æ—G“Ò&6öÆÆ6VB"ÀÐ¢Ð¢v—F‚7Bæ6öçF–æW"†¶W“Ò'v÷&·76U÷6†VÆÂ"“ Ð¢–b&–Ö'•÷f–WrÓÒ%&VvVçB–çF¶R# Ð¢&VæFW%öFE÷F"‚Ð¢VÇ6S Ð¢&VæFW%÷VW'•÷F"‚Ð Ð Ð¦–bõöæÖUõòÓÒ%õöÖ–åõò# Ð¢Ö–â‚Ð