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
    "Brønsted acid",
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
            border-radius: var(--radius-card);
            box-shadow: var(--shadow);
            gap: var(--space-2);
            overflow: hidden;
            padding: 20px;
        }

        .st-key-upload_panel > div,
        .st-key-review_placeholder > div,
        .st-key-registration_panel > div,
        .st-key-query_panel > div {
            padding: 0;
        }

        div[data-testid="stFileUploader"] section {
            background:
                linear-gradient(90deg, rgba(8, 122, 112, .025) 1px, transparent 1px),
                linear-gradient(rgba(8, 122, 112, .025) 1px, transparent 1px),
                #f8fbfc;
            background-size: 20px 20px;
            border: 1px dashed var(--line-strong);
            border-radius: var(--radius-control);
            min-height: 142px;
            padding: 24px;
            transition: border-color .18s ease, background .18s ease,
                transform .18s ease;
        }

        div[data-testid="stFileUploader"] section:hover {
            background: #fff;
            border-color: var(--teal);
            transform: translateY(-1px);
        }

        div[data-testid="stFileUploader"] button,
        div.stButton > button,
        div[data-testid="stDownloadButton"] > button {
            border-radius: 10px;
            font-weight: 680;
            min-height: 44px;
            transition: background-color .18s ease, border-color .18s ease,
                color .18s ease, box-shadow .18s ease, transform .18s ease;
        }

        div[data-testid="stFileUploader"] button,
        div.stButton > button[kind="secondary"],
        div.stButton > button[kind="tertiary"],
        div[data-testid="stDownloadButton"] > button {
            background: #fff !important;
            border: 1px solid var(--line-strong) !important;
            color: var(--ink) !important;
        }

        div[data-testid="stFileUploader"] button:hover,
        div.stButton > button[kind="secondary"]:hover,
        div.stButton > button[kind="tertiary"]:hover,
        div[data-testid="stDownloadButton"] > button:hover {
            background: #f0f0f2 !important;
            border-color: rgba(0, 0, 0, 0.22) !important;
            color: #000 !important;
        }

        div.stButton > button[kind="primary"] {
            background: var(--accent) !important;
            border-color: var(--accent) !important;
            color: #fff !important;
        }

        button[data-testid="stBaseButton-primary"] {
            background: var(--accent) !important;
            border-color: var(--accent) !important;
            color: #fff !important;
        }

        button[data-testid="stBaseButton-primary"]:hover {
            background: var(--accent-hover) !important;
            border-color: var(--accent-hover) !important;
            color: #fff !important;
        }

        button[data-testid="stBaseButton-secondary"],
        button[data-testid="stBaseButton-tertiary"] {
            background: #fff !important;
            border-color: var(--line-strong) !important;
            color: var(--ink) !important;
        }

        button[data-testid="stBaseButton-secondary"]:hover,
        button[data-testid="stBaseButton-tertiary"]:hover {
            background: #f0f0f2 !important;
            border-color: rgba(0, 0, 0, 0.22) !important;
            color: #000 !important;
        }

        button[data-testid^="stBaseButton"] p,
        button[data-testid^="stBaseButton"] span {
            color: inherit !important;
        }

        div.stButton > button[kind="primary"]:hover {
            background: var(--accent-hover) !important;
            border-color: var(--accent-hover) !important;
            color: #fff !important;
            box-shadow: 0 5px 16px rgba(0, 113, 227, 0.22);
        }

        div[data-testid="stFileUploader"] button p,
        div[data-testid="stFileUploader"] button span,
        div.stButton > button p,
        div.stButton > button span,
        div[data-testid="stDownloadButton"] > button p,
        div[data-testid="stDownloadButton"] > button span {
            color: inherit !important;
        }

        div.stButton > button:disabled {
            background: #e8e8ed !important;
            border-color: #e8e8ed !important;
            color: #5f5f65 !important;
            opacity: 1 !important;
        }

        div.stButton > button:focus-visible,
        div[data-testid="stDownloadButton"] > button:focus-visible,
        input:focus-visible,
        textarea:focus-visible {
            outline: 3px solid rgba(0, 113, 227, 0.25) !important;
            outline-offset: 2px;
        }

        div[data-baseweb="input"] > div,
        div[data-baseweb="select"] > div,
        textarea {
            background: #fff !important;
            border-color: var(--line-strong) !important;
            border-radius: var(--radius-control) !important;
        }

        div[data-testid="stTextInputRootElement"],
        div[data-testid="stNumberInputContainer"],
        div[data-testid="stSelectbox"] [role="group"],
        div[data-testid="stDateInput"] [data-baseweb="input"] {
            background: #f6f8fa !important;
            border: 1px solid #d2d2d7 !important;
            border-radius: 12px !important;
            box-shadow: none !important;
            min-height: 44px;
            transition: background-color .16s ease, border-color .16s ease,
                box-shadow .16s ease;
        }

        div[data-testid="stTextArea"] textarea {
            background: #f6f8fa !important;
            border: 1px solid #d2d2d7 !important;
            border-radius: var(--radius-control) !important;
            box-shadow: none !important;
            padding: 14px 16px !important;
            transition: background-color .16s ease, border-color .16s ease,
                box-shadow .16s ease;
        }

        div[data-testid="stTextInputRootElement"]:focus-within,
        div[data-testid="stNumberInputContainer"]:focus-within,
        div[data-testid="stSelectbox"] [role="group"]:focus-within,
        div[data-testid="stDateInput"] [data-baseweb="input"]:focus-within,
        div[data-testid="stTextArea"] textarea:focus {
            background: #fff !important;
            border-color: var(--accent) !important;
            box-shadow: 0 0 0 3px rgba(0, 113, 227, 0.14) !important;
        }

        div[data-testid="stTextInputRootElement"] input,
        div[data-testid="stNumberInputContainer"] input,
        div[data-testid="stSelectbox"] [role="group"] input,
        div[data-testid="stDateInput"] input,
        div[data-testid="stDateInput"] [data-baseweb="base-input"] {
            background: transparent !important;
            border: 0 !important;
        }

        input, textarea {
            color: var(--ink) !important;
        }

        input::placeholder, textarea::placeholder {
            color: var(--secondary) !important;
            opacity: 1 !important;
        }

        div[data-baseweb="select"] span {
            color: var(--ink);
        }

        div[data-testid="stWidgetLabel"] p,
        div[data-testid="stWidgetLabel"] span,
        label p,
        label span {
            color: #3a3a3c !important;
        }

        div[data-testid="stSegmentedControl"] {
            margin: 0 0 var(--space-4);
            overflow-x: auto;
            padding-bottom: 2px;
        }

        div[data-testid="stSegmentedControl"] > div {
            background: rgba(118, 118, 128, 0.11);
            border: 1px solid rgba(0, 0, 0, 0.06);
            border-radius: 13px;
            min-width: max-content;
            padding: 4px;
        }

        div[data-testid="stSegmentedControl"] button {
            border-radius: 9px !important;
            color: var(--secondary) !important;
            min-height: 42px;
        }

        div[data-testid="stSegmentedControl"] button[aria-pressed="true"] {
            background: #fff !important;
            box-shadow: 0 1px 4px rgba(0, 0, 0, 0.12);
            color: var(--ink) !important;
        }

        div[data-testid="stSegmentedControl"] button p,
        div[data-testid="stSegmentedControl"] button span {
            color: inherit !important;
        }

        div[data-testid="stButtonGroup"] {
            margin: 0 0 var(--space-4);
            overflow-x: auto;
            padding-bottom: 2px;
        }

        div[data-testid="stButtonGroup"] [role="radiogroup"] {
            background: rgba(118, 118, 128, 0.11);
            border: 1px solid rgba(0, 0, 0, 0.06);
            border-radius: 13px;
            min-width: max-content;
            padding: 4px;
        }

        div[data-testid="stButtonGroup"] button[data-variant="segmented_control"] {
            border-radius: 9px !important;
            color: var(--secondary) !important;
            min-height: 42px;
        }

        div[data-testid="stButtonGroup"] button[data-variant="segmented_control"][data-selected],
        div[data-testid="stButtonGroup"] button[data-variant="segmented_control"][aria-checked="true"] {
            background: #fff !important;
            box-shadow: 0 1px 4px rgba(0, 0, 0, 0.12);
            color: var(--ink) !important;
        }

        div[data-testid="stButtonGroup"] button p,
        div[data-testid="stButtonGroup"] button span {
            color: inherit !important;
        }

        div[data-testid="stPills"] {
            overflow: visible;
        }

        div[data-testid="stPills"] [role="radiogroup"] {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            min-width: 0;
            overflow: visible;
        }

        div[data-testid="stPills"] button {
            background: #fff !important;
            border: 1px solid var(--line-strong) !important;
            border-radius: 999px !important;
            color: var(--secondary) !important;
            flex: 0 1 auto;
            min-height: 38px;
            min-width: 0;
        }

        div[data-testid="stPills"] button[aria-checked="true"],
        div[data-testid="stPills"] button[data-selected] {
            background: var(--accent-soft) !important;
            border-color: rgba(25, 87, 210, .34) !important;
            color: var(--accent) !important;
        }

        div[data-testid="stExpander"] summary,
        div[data-testid="stExpander"] summary p,
        div[data-testid="stExpander"] summary span {
            color: var(--ink) !important;
        }

        .empty-state {
            align-items: flex-start;
            background: #f8fafb;
            border: 1px solid var(--line);
            border-radius: var(--radius-control);
            color: var(--secondary);
            display: flex;
            justify-content: center;
            flex-direction: column;
            min-height: 112px;
            padding: var(--space-4);
            text-align: left;
        }

        .empty-state-mark {
            align-items: center;
            background: var(--accent-soft);
            border-radius: 10px;
            color: var(--accent);
            display: flex;
            font-size: 12px;
            font-weight: 760;
            height: 34px;
            justify-content: center;
            margin-bottom: 12px;
            width: 34px;
        }

        .empty-state-title {
            color: var(--ink);
            font-size: 16px;
            font-weight: 720;
            margin-bottom: 4px;
        }

        .empty-state-copy {
            color: var(--secondary);
            font-size: 13px;
            line-height: 1.5;
            max-width: 620px;
        }

        .upload-hint {
            align-items: flex-start;
            background: var(--teal-soft);
            border: 1px solid rgba(8, 122, 112, .14);
            border-radius: 10px;
            color: #285e5a;
            display: flex;
            font-size: 13px;
            line-height: 1.5;
            margin: 12px 0 0;
            padding: 10px 12px;
            text-align: left;
        }

        .preview-list {
            display: grid;
            gap: 0;
            margin-top: 4px;
        }

        .preview-list > div {
            align-items: center;
            border-top: 1px solid var(--line);
            display: flex;
            gap: 14px;
            min-height: 54px;
        }

        .preview-list span {
            color: var(--accent);
            font-size: 11px;
            font-weight: 700;
        }

        .preview-list strong {
            color: var(--ink);
            font-size: 14px;
            font-weight: 620;
        }

        .meta-grid {
            display: grid;
            gap: 10px;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            margin-top: 13px;
        }

        .upload-meta {
            align-items: center;
            background: rgba(245, 245, 247, 0.78);
            border-radius: var(--radius-control);
            display: grid;
            gap: 5px;
            padding: 10px 12px;
        }

        .compact-upload-header {
            min-width: 0;
        }

        .compact-upload-header .section-eyebrow {
            color: var(--green);
            margin-bottom: 5px;
        }

        .compact-upload-title {
            color: var(--ink);
            font-size: 22px;
            font-weight: 680;
            letter-spacing: -0.035em;
            line-height: 1.12;
            margin: 0;
        }

        .compact-upload-file {
            color: var(--secondary);
            font-size: 12px;
            line-height: 1.45;
            margin: 5px 0 0;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }

        .st-key-label_preview,
        .st-key-compact_label_preview {
            background: rgba(245, 245, 247, 0.72);
            border: 1px solid var(--line);
            border-radius: 18px;
            overflow: hidden;
            padding: 8px;
        }

        .st-key-label_preview > div[data-testid="stVerticalBlock"],
        .st-key-compact_label_preview > div[data-testid="stVerticalBlock"] {
            gap: 0;
        }

        .st-key-label_preview [data-testid="stImage"] img,
        .st-key-label_preview [data-testid="stImageContainer"] img {
            display: block;
            max-height: 320px;
            object-fit: contain;
            width: 100%;
        }

        .st-key-compact_label_preview [data-testid="stImage"] img,
        .st-key-compact_label_preview [data-testid="stImageContainer"] img {
            display: block;
            max-height: 156px;
            object-fit: contain;
            width: 100%;
        }

        .st-key-replace_label_image div[data-testid="stExpander"] {
            margin: 0;
        }

        .st-key-replace_label_image div[data-testid="stExpander"] summary {
            min-height: 42px;
        }

        .upload-meta-name {
            align-items: baseline;
            display: flex;
            gap: 10px;
            min-width: 0;
        }

        .upload-meta-name span {
            color: var(--secondary);
            flex: 0 0 auto;
            font-size: 11px;
            font-weight: 620;
        }

        .upload-meta-name strong {
            color: var(--ink);
            font-size: 13px;
            font-weight: 640;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }

        .upload-meta-detail {
            color: var(--secondary);
            font-size: 11px;
            line-height: 1.4;
        }

        .summary-grid {
            display: grid;
            align-items: start;
            gap: 8px;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            margin-top: 10px;
        }

        .meta-item, .summary-item {
            background: rgba(245, 245, 247, 0.72);
            border-radius: 13px;
            padding: 10px 12px;
        }

        .meta-label, .summary-label {
            color: var(--secondary);
            font-size: 11px;
            font-weight: 620;
            margin-bottom: 4px;
        }

        .meta-value, .summary-value {
            color: var(--ink);
            font-size: 14px;
            font-weight: 620;
            overflow-wrap: anywhere;
        }

        .status-line {
            align-items: center;
            background: rgba(36, 138, 61, 0.08);
            border-radius: 13px;
            color: #1f7535;
            display: flex;
            font-size: 13px;
            font-weight: 600;
            gap: 9px;
            margin: 2px 0 6px;
            padding: 10px 12px;
        }

        .status-line.neutral {
            background: var(--accent-soft);
            color: #244f9b;
        }

        .status-line.neutral .status-dot {
            background: var(--accent);
        }

        .review-summary {
            display: grid;
            gap: var(--space-2);
            margin-top: 10px;
        }

        .review-summary-group {
            display: grid;
            gap: 8px;
        }

        .review-summary-heading {
            color: var(--secondary);
            font-size: 11px;
            font-weight: 700;
            letter-spacing: .07em;
            text-transform: uppercase;
        }

        .review-identity-grid {
            display: grid;
            gap: 8px;
            grid-template-columns: repeat(3, minmax(0, 1fr));
        }

        .review-summary-stack {
            display: grid;
            gap: 8px;
        }

        .review-summary-stack .summary-item {
            min-height: 0;
        }

        .summary-chip-row {
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
            margin-top: 7px;
        }

        .summary-chip {
            background: rgba(0, 113, 227, 0.08);
            border-radius: 999px;
            color: #0068d1;
            display: inline-flex;
            font-size: 12px;
            font-weight: 620;
            line-height: 1.35;
            padding: 5px 8px;
        }

        .summary-chip.constraint {
            background: rgba(169, 93, 0, 0.09);
            color: #8a4c00;
        }

        .storage-location-card {
            align-items: center;
            background: rgba(36, 138, 61, 0.08);
            border: 1px solid rgba(31, 117, 53, 0.14);
            border-radius: 13px;
            display: flex;
            justify-content: space-between;
            gap: 14px;
            padding: 11px 12px;
        }

        .storage-location-card .summary-label {
            margin-bottom: 0;
        }

        .storage-location-card .summary-value {
            color: #1f7535;
            text-align: right;
        }

        .storage-rule {
            align-items: flex-start;
            display: flex;
            gap: 9px;
            margin-top: 7px;
        }

        .storage-rule-code {
            background: rgba(0, 0, 0, 0.07);
            border-radius: 7px;
            color: var(--ink);
            flex: 0 0 auto;
            font-size: 11px;
            font-weight: 700;
            letter-spacing: .02em;
            padding: 4px 7px;
        }

        .storage-rule-copy {
            color: var(--ink);
            font-size: 13px;
            font-weight: 560;
            line-height: 1.45;
        }

        .status-dot {
            background: var(--green);
            border-radius: 50%;
            height: 7px;
            width: 7px;
        }

        .status-line.warning {
            background: rgba(169, 93, 0, 0.09);
            color: #8a4c00;
        }

        .status-line.warning .status-dot {
            background: var(--amber);
        }

        .tag-row {
            display: flex;
            flex-wrap: wrap;
            gap: 7px;
            margin: 10px 0 15px;
        }

        .tag {
            background: rgba(8, 127, 117, 0.09);
            border-radius: 999px;
            color: #087268;
            font-size: 12px;
            font-weight: 620;
            padding: 6px 10px;
        }

        .safety-card {
            background: linear-gradient(145deg, rgba(0, 102, 204, 0.07), rgba(255, 255, 255, 0.92));
            border: 1px solid rgba(0, 102, 204, 0.16);
            border-radius: 18px;
            margin: 4px 0 18px;
            padding: 18px;
        }

        .safety-kicker, .decision-route, .query-route {
            color: var(--accent);
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 0.06em;
            text-transform: uppercase;
        }

        .safety-title {
            color: var(--ink);
            font-size: 18px;
            font-weight: 660;
            letter-spacing: -0.02em;
            margin: 4px 0 5px;
        }

        .decision-card {
            background: #f5f5f7;
            border: 1px solid var(--line);
            border-radius: 18px;
            margin: 10px 0 14px;
            padding: 18px;
        }

        .decision-location {
            color: var(--ink);
            font-size: 22px;
            font-weight: 680;
            letter-spacing: -0.03em;
            margin: 5px 0;
        }

        .query-trace {
            display: grid;
            gap: 10px;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            margin: 12px 0 16px;
        }

        .trace-step {
            background: #f5f5f7;
            border: 1px solid var(--line);
            border-radius: 14px;
            color: var(--secondary);
            font-size: 12px;
            line-height: 1.4;
            padding: 12px;
        }

        .trace-step strong {
            color: var(--ink);
            display: block;
            font-size: 13px;
            margin-bottom: 3px;
        }

        .order-card {
            background: rgba(245, 245, 247, 0.72);
            border: 1px solid var(--line);
            border-radius: 16px;
            margin-bottom: 10px;
            padding: 16px;
        }

        .order-card.selected {
            background: rgba(0, 113, 227, 0.055);
            border-color: rgba(0, 113, 227, 0.28);
        }

        .order-id {
            color: var(--accent);
            font-size: 12px;
            font-weight: 650;
        }

        .order-name {
            color: var(--ink);
            font-size: 18px;
            font-weight: 650;
            margin: 5px 0 3px;
        }

        .order-detail {
            color: var(--secondary);
            font-size: 13px;
            line-height: 1.5;
        }

        .metric-row {
            display: grid;
            gap: 12px;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            margin: 8px 0 18px;
        }

        .metric-card {
            background: var(--surface-strong);
            border: 1px solid var(--line);
            border-radius: 12px;
            padding: 16px;
        }

        .metric-value {
            color: var(--ink);
            font-size: 28px;
            font-weight: 680;
            letter-spacing: -0.04em;
        }

        .metric-label {
            color: var(--secondary);
            font-size: 12px;
            margin-top: 4px;
        }

        .quiet-note {
            color: var(--secondary);
            font-size: 13px;
            line-height: 1.5;
            margin: 8px 0;
        }

        .confirmation {
            background: linear-gradient(145deg, rgba(0, 113, 227, 0.075), rgba(8, 127, 117, 0.055));
            border: 1px solid rgba(0, 113, 227, 0.18);
            border-radius: 18px;
            padding: 20px;
        }

        .confirmation-id {
            color: var(--accent);
            font-size: 12px;
            font-weight: 650;
            margin-bottom: 6px;
        }

        .confirmation-title {
            color: var(--ink);
            font-size: 22px;
            font-weight: 670;
            letter-spacing: -0.03em;
        }

        .stAlert {
            border-radius: 14px;
        }

        div[data-testid="stDataFrame"] {
            border: 1px solid var(--line);
            border-radius: 16px;
            overflow: hidden;
        }

        div[data-testid="stCode"] {
            background: #f5f5f7 !important;
            border: 1px solid var(--line) !important;
            border-radius: var(--radius-control) !important;
            overflow: hidden;
        }

        div[data-testid="stCode"] pre,
        div[data-testid="stCode"] code,
        div[data-testid="stCode"] span {
            color: var(--ink) !important;
        }

        /* Primary workspace navigation */
        .st-key-primary_view {
            background: transparent;
            margin: 0 0 var(--space-5);
            max-width: none;
            padding: 0;
            position: static;
            z-index: auto;
        }

        .st-key-primary_view div[data-testid="stButtonGroup"],
        .st-key-primary_view div[data-testid="stSegmentedControl"] {
            margin: 0;
            overflow: visible;
            padding: 0;
        }

        .st-key-primary_view [role="radiogroup"],
        .st-key-primary_view div[data-testid="stSegmentedControl"] > div {
            background: transparent;
            border: 0;
            border-bottom: 1px solid var(--line);
            border-radius: 0;
            box-shadow: none;
            display: flex;
            margin: 0 auto;
            max-width: 640px;
            min-width: 0;
            padding: 0;
            width: 100%;
        }

        .st-key-primary_view div[data-testid="stButtonGroup"] [role="radiogroup"] {
            background: transparent !important;
            border: 0 !important;
            border-bottom: 1px solid var(--line) !important;
            border-radius: 0 !important;
            box-shadow: none !important;
            max-width: 640px;
            padding: 0 !important;
            width: 100%;
        }

        .st-key-primary_view button[data-variant="segmented_control"],
        .st-key-primary_view div[data-testid="stSegmentedControl"] button {
            border: 1px solid transparent !important;
            border-bottom: 3px solid transparent !important;
            border-radius: 0 !important;
            background: transparent !important;
            flex: 1 1 50%;
            font-size: 14px;
            font-weight: 680;
            height: 46px !important;
            min-height: 46px !important;
            min-width: 0;
        }

        .st-key-primary_view div[data-testid="stButtonGroup"]
        button[data-variant="segmented_control"] {
            background: transparent !important;
            border: 0 !important;
            border-bottom: 3px solid transparent !important;
            border-radius: 0 !important;
            box-shadow: none !important;
        }

        .st-key-primary_view button[data-variant="segmented_control"][data-selected],
        .st-key-primary_view button[data-variant="segmented_control"][aria-checked="true"],
        .st-key-primary_view div[data-testid="stSegmentedControl"] button[aria-pressed="true"] {
            border-color: transparent !important;
            border-bottom-color: var(--accent) !important;
            box-shadow: none !important;
            color: var(--accent) !important;
        }

        .st-key-primary_view div[data-testid="stButtonGroup"]
        button[data-variant="segmented_control"][data-selected],
        .st-key-primary_view div[data-testid="stButtonGroup"]
        button[data-variant="segmented_control"][aria-checked="true"] {
            background: transparent !important;
            border-bottom-color: var(--accent) !important;
            box-shadow: none !important;
            color: var(--accent) !important;
        }

        .st-key-workspace_shell {
            margin: 0;
        }

        .st-key-workspace_shell > div[data-testid="stVerticalBlock"] {
            gap: var(--space-3);
        }

        .st-key-intake_start {
            margin: var(--space-1) auto 0;
            max-width: 680px;
        }

        .st-key-intake_workspace .st-key-upload_panel {
            position: sticky;
            top: 16px;
        }

        .st-key-query_mode {
            max-width: 560px;
        }

        .st-key-query_mode [role="radiogroup"],
        .st-key-query_mode div[data-testid="stSegmentedControl"] > div {
            display: flex;
            width: 100%;
        }

        .st-key-query_mode button[data-variant="segmented_control"],
        .st-key-query_mode div[data-testid="stSegmentedControl"] button {
            border: 1px solid transparent !important;
            flex: 1 1 50%;
            font-weight: 620;
            min-height: 44px !important;
            min-width: 0;
            white-space: normal !important;
        }

        .st-key-query_mode button[data-variant="segmented_control"][data-selected],
        .st-key-query_mode button[data-variant="segmented_control"][aria-checked="true"],
        .st-key-query_mode div[data-testid="stSegmentedControl"] button[aria-pressed="true"] {
            border-color: transparent !important;
        }

        .st-key-query_panel {
            margin-top: 0;
        }

        .verification-boundary {
            display: grid;
            gap: var(--space-1);
            padding: 2px 0 var(--space-1);
        }

        .verification-boundary strong {
            color: var(--ink);
            font-size: 15px;
            font-weight: 650;
        }

        .verification-boundary span {
            color: var(--secondary);
            font-size: 13px;
            line-height: 1.55;
        }

        .query-ready {
            align-items: flex-start;
            background: #f8fafb;
            border: 1px solid var(--line);
            border-radius: var(--radius-control);
            color: var(--secondary);
            display: flex;
            font-size: 14px;
            justify-content: center;
            min-height: 88px;
            padding: var(--space-4);
            text-align: left;
        }

        .metric-row {
            gap: var(--space-3);
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            margin: var(--space-3) 0 var(--space-4);
        }

        .metric-card {
            border-radius: 20px;
            padding: 20px;
        }

        .summary-grid {
            gap: 8px;
            grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
            margin-top: 10px;
        }

        .query-trace {
            gap: var(--space-2);
            grid-template-columns: repeat(auto-fit, minmax(155px, 1fr));
            margin: var(--space-3) 0 var(--space-4);
        }

        .status-line,
        .safety-card,
        .decision-card,
        .quiet-note {
            margin-left: 0;
            margin-right: 0;
        }

        .confirmation,
        .order-card.selected {
            animation: surfaceIn .28s cubic-bezier(.22, 1, .36, 1) both;
        }

        @keyframes heroRise {
            from {
                opacity: 0;
                transform: translateY(14px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }

        @keyframes surfaceIn {
            from {
                opacity: 0;
                transform: translateY(8px) scale(.995);
            }
            to {
                opacity: 1;
                transform: translateY(0) scale(1);
            }
        }

        .hero-kicker {
            animation: heroRise .42s cubic-bezier(.22, 1, .36, 1) both;
        }

        .hero-title {
            animation: heroRise .52s .05s cubic-bezier(.22, 1, .36, 1) both;
        }

        .hero-copy {
            animation: heroRise .52s .11s cubic-bezier(.22, 1, .36, 1) both;
        }

        .capability-rail {
            animation: heroRise .55s .17s cubic-bezier(.22, 1, .36, 1) both;
        }

        div.stButton > button:not(:disabled):hover,
        div[data-testid="stDownloadButton"] > button:not(:disabled):hover {
            transform: translateY(-1px);
        }

        div.stButton > button:not(:disabled):active,
        div[data-testid="stDownloadButton"] > button:not(:disabled):active {
            transform: scale(.985);
        }

        @media (max-width: 820px) {
            div.block-container {
                padding: .75rem 1rem 3.5rem;
            }

            .hero {
                gap: 20px;
                grid-template-columns: 1fr;
                padding: 26px 0 20px;
            }

            .hero-title {
                font-size: clamp(38px, 8vw, 48px);
            }

            .hero-copy {
                font-size: 16px;
                margin-top: 16px;
            }

            .capability-rail {
                display: grid;
                grid-template-columns: repeat(3, minmax(0, 1fr));
                padding: 4px;
            }

            .capability {
                border: 0;
                padding: 12px;
            }

            .capability + .capability {
                border-left: 1px solid var(--line);
                border-top: 0;
            }

            .st-key-primary_view {
                margin-bottom: var(--space-5);
            }

            .st-key-primary_view button[data-variant="segmented_control"],
            .st-key-primary_view div[data-testid="stSegmentedControl"] button {
                font-size: 13px;
                height: 44px !important;
                min-height: 44px !important;
            }

            .stepper {
                display: grid;
                gap: 0;
                grid-template-columns: repeat(5, minmax(0, 1fr));
                margin-top: 8px;
                overflow: visible;
                padding-bottom: 4px;
            }

            .step {
                font-size: 10px;
                min-width: 0;
                padding-left: 0;
                padding-right: 0;
                text-align: center;
            }

            .step strong {
                font-size: 10px;
                margin-right: 0;
            }

            .st-key-intake_workspace > div[data-testid="stVerticalBlock"] >
            div[data-testid="stHorizontalBlock"] {
                flex-direction: column;
            }

            .st-key-intake_workspace > div[data-testid="stVerticalBlock"] >
            div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"] {
                flex: 1 1 auto !important;
                width: 100% !important;
            }

            .st-key-intake_workspace .st-key-upload_panel {
                position: static;
            }

            .meta-grid {
                grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
            }

            .query-trace {
                grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
            }

            .summary-grid {
                grid-template-columns: repeat(auto-fit, minmax(145px, 1fr));
            }

            .review-identity-grid {
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }

            .st-key-upload_panel,
            .st-key-review_placeholder,
            .st-key-registration_panel,
            .st-key-query_panel {
                padding: 16px;
            }
        }

        @media (max-width: 460px) {
            div.block-container {
                padding-left: .85rem;
                padding-right: .85rem;
            }

            .brand-subtitle {
                display: none;
            }

            .topbar-note {
                display: flex;
                font-size: 11px;
                padding: 6px 8px;
            }

            .capability-rail {
                display: grid;
                grid-template-columns: repeat(3, minmax(0, 1fr));
            }

            .hero {
                align-items: flex-start;
                gap: 16px;
                padding: 22px 0 18px;
                text-align: left;
            }

            .hero-title {
                font-size: 32px;
                line-height: 1.03;
            }

            .hero-title br {
                display: none;
            }

            .hero-copy {
                font-size: 15px;
                margin-left: 0;
            }

            .capability {
                display: flex;
                gap: 6px;
                padding: 8px 6px;
            }

            .capability > span {
                flex: 0 0 24px;
                font-size: 9px;
                height: 24px;
                width: 24px;
            }

            .capability strong {
                font-size: 10px;
                line-height: 1.2;
            }

            .capability small {
                display: none;
            }

            .section-title {
                font-size: 28px;
            }

            .review-identity-grid {
                grid-template-columns: 1fr;
            }

            .storage-location-card {
                align-items: flex-start;
                flex-direction: column;
                gap: 4px;
            }

            .storage-location-card .summary-value {
                text-align: left;
            }

            .st-key-primary_view button[data-variant="segmented_control"],
            .st-key-primary_view div[data-testid="stSegmentedControl"] button {
                font-size: 12.5px;
                padding-left: 8px !important;
                padding-right: 8px !important;
            }

            .st-key-query_mode button[data-variant="segmented_control"],
            .st-key-query_mode div[data-testid="stSegmentedControl"] button {
                font-size: 12px;
                line-height: 1.2;
                padding-left: 6px !important;
                padding-right: 6px !important;
            }

            div[data-testid="stPills"] button {
                flex: 1 1 120px;
                justify-content: center;
            }

            .step {
                font-size: 9px;
                line-height: 1.2;
            }

            .metric-row {
                gap: 8px;
                grid-template-columns: repeat(3, minmax(0, 1fr));
            }

            .metric-card {
                padding: 12px 10px;
            }

            .metric-value {
                font-size: 22px;
            }

            .metric-label {
                font-size: 10px;
            }
        }

        @media (prefers-reduced-motion: reduce) {
            *,
            *::before,
            *::after {
                animation-duration: .01ms !important;
                animation-iteration-count: 1 !important;
                scroll-behavior: auto !important;
                transition-duration: .01ms !important;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def escaped(value: Any) -> str:
    return html.escape(str(value))


def format_file_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes / (1024 * 1024):.1f} MB"


def uploaded_file_signature(contents: bytes) -> str:
    return hashlib.sha256(contents).hexdigest()


def get_sample_extraction_result() -> dict[str, Any]:
    """Return a blank, editable intake state; never a fake reagent record."""
    return {
        "chemical_name": "",
        "cas_number": "",
        "specification": "",
        "batch_number": "",
        "manufacturer": "",
        "expiry_date": None,
        "quantity": 0.0,
        "unit": "mL",
        "confidence": 0,
    }


def streamlit_provider_environment() -> dict[str, str]:
    """Read provider settings from the process and Streamlit secrets safely."""

    environment = {
        name: value
        for name in PROVIDER_ENV_NAMES
        if isinstance((value := os.environ.get(name)), str)
    }
    try:
        for name in PROVIDER_ENV_NAMES:
            value = st.secrets.get(name)
            if value is not None:
                environment[name] = str(value)
    except (FileNotFoundError, KeyError, AttributeError):
        # A local installation may intentionally not have a secrets file.
        pass
    return environment


def get_chemical_classification(cas_number: str | None) -> dict[str, Any]:
    """Return a reviewed CAS profile or a fail-closed manual-review state."""
    normalized = (cas_number or "").strip()
    cached = get_cas_classification(normalized) if validate_cas_number(normalized) else None
    if cached:
        return {
            "labels": list(cached["chemical_tags"]),
            "constraints": list(cached["hazard_labels"]),
            "cas_number": normalized,
            "confidence": float(cached.get("confidence") or 0),
            "rationale": cached.get("rationale") or "CAS classification cache.",
            "cache_status": (
                "Reviewer-confirmed CAS cache"
                if cached.get("reviewed")
                else "CAS classification cache"
            ),
        }
    profile = catalog_profile(normalized)
    if profile:
        return {
            "labels": list(profile["labels"]),
            "constraints": list(profile["constraints"]),
            "cas_number": normalized,
            "confidence": float(profile["confidence"]),
            "rationale": str(profile["rationale"]),
            "cache_status": "Reviewed reference profile",
        }
    return {
        "cas_number": normalized,
        "labels": [],
        "constraints": [],
        "confidence": 0.0,
        "rationale": "No cached profile is available. A chemistry review is required.",
        "cache_status": "Manual classification required",
    }


def get_sample_storage_recommendation(
    cas_number: str | None = "64-17-5",
) -> dict[str, Any]:
    classification = get_chemical_classification(cas_number)
    decision = determine_storage_location(classification["constraints"])
    return {
        "tags": classification["labels"],
        "constraints": classification["constraints"],
        "recommended_location": decision["location"],
        "reason": decision["rule"],
        "classification": classification,
    }


def confirm_sample_registration(
    payload: dict[str, Any], *, reviewed: bool, db_path: str | None = None
) -> dict[str, Any]:
    """Commit one reviewed reagent through the backend's idempotent intake path."""

    return register_reagent_payload(payload, reviewed=reviewed, db_path=db_path)


def clear_state_keys(
    state: MutableMapping[str, Any],
    keys: set[str] | frozenset[str] = frozenset(ADD_STATE_KEYS),
) -> None:
    for key in keys:
        state.pop(key, None)


def preserve_add_workflow_state(
    state: MutableMapping[str, Any] | None = None,
) -> None:
    """Keep stage-specific widget values when their controls leave the screen."""
    target = st.session_state if state is None else state
    for key in ADD_STATE_KEYS:
        if key in target:
            target[key] = target[key]


def reset_add_workflow(state: MutableMapping[str, Any] | None = None) -> None:
    target = st.session_state if state is None else state
    clear_state_keys(target)
    target["add_upload_nonce"] = int(target.get("add_upload_nonce", 0)) + 1


def can_confirm_registration(reviewed: bool, extraction_complete: bool) -> bool:
    return bool(reviewed and extraction_complete)


def validate_cas_number(cas_number: str | None) -> bool:
    """Validate CAS format and its built-in check digit locally."""
    value = (cas_number or "").strip()
    parts = value.split("-")
    if (
        len(parts) != 3
        or not all(part.isdigit() for part in parts)
        or not 2 <= len(parts[0]) <= 7
        or len(parts[1]) != 2
        or len(parts[2]) != 1
    ):
        return False
    body = f"{parts[0]}{parts[1]}"
    checksum = sum(
        int(digit) * multiplier
        for multiplier, digit in enumerate(reversed(body), start=1)
    )
    return checksum % 10 == int(parts[2])


def cas_display_state(cas_number: str | None) -> tuple[str, str]:
    value = (cas_number or "").strip()
    if not value:
        return "CAS number required", "warning"
    if validate_cas_number(value):
        return "CAS check digit verified", "positive"
    return "CAS check digit failed · recapture or enter manually", "warning"


def load_sample_inventory(
    today: date | None = None,
    *,
    db_path: str | None = None,
) -> pd.DataFrame:
    """Load actual reagent lots from the inventory database.

    The empty state is intentional: this interface no longer invents sample
    stock. Register or import real records before running inventory searches.
    """

    return load_inventory_frame(today=today, db_path=db_path)


def filter_sample_inventory(
    frame: pd.DataFrame,
    *,
    search_text: str = "",
    manufacturer: str = "All manufacturers",
    storage_location: str = "All locations",
    expiry_state: str = "All expiry states",
    minimum_quantity: int = 0,
) -> pd.DataFrame:
    filtered = frame.copy()
    query = search_text.strip().lower()
    if query:
        searchable_columns = [
            "Record ID",
            "Chemical name",
            "CAS number",
            "Manufacturer",
            "Batch number",
            "Specification",
        ]
        mask = filtered[searchable_columns].astype(str).apply(
            lambda column: column.str.lower().str.contains(query, regex=False)
        )
        filtered = filtered[mask.any(axis=1)]
    if manufacturer != "All manufacturers":
        filtered = filtered[filtered["Manufacturer"] == manufacturer]
    if storage_location != "All locations":
        filtered = filtered[filtered["Storage location"] == storage_location]
    if expiry_state != "All expiry states":
        filtered = filtered[filtered["Expiry state"] == expiry_state]
    filtered = filtered[filtered["Quantity"] >= minimum_quantity]
    return filtered.reset_index(drop=True)


def empty_inventory_result(frame: pd.DataFrame) -> pd.DataFrame:
    return frame.iloc[0:0].copy().reset_index(drop=True)


def compile_structured_query(query: str, frame: pd.DataFrame) -> dict[str, Any]:
    """Compile an allowlisted inventory intent into a verified loaded-record filter."""
    normalized = query.lower().strip()
    empty = empty_inventory_result(frame)
    if not normalized:
        return {
            "route": "unsupported",
            "route_label": "Needs a question",
            "interpretation": "Enter an inventory or chemistry question to begin.",
            "query_code": "",
            "parameters": [],
            "results": empty,
            "warning": "",
        }

    chemical_aliases = {
        "dcm": "Dichloromethane",
        "dichloromethane": "Dichloromethane",
    }
    for chemical_name in frame.get("Chemical name", pd.Series(dtype=str)).dropna().unique():
        name = str(chemical_name).strip()
        if name:
            chemical_aliases[name.lower()] = name
    requested_chemical = next(
        (
            canonical
            for alias, canonical in chemical_aliases.items()
            if alias in normalized
        ),
        None,
    )
    if requested_chemical:
        result = frame[
            (frame["Chemical name"].str.lower() == requested_chemical.lower())
            & (frame["Quantity"] > 0)
            & (frame["Status"] != "Expired")
        ]
        return {
            "route": "structured",
            "route_label": "Structured inventory query",
            "interpretation": (
                f"Current on-hand inventory records for {requested_chemical}."
            ),
            "query_code": (
                "Loaded inventory filter\n"
                "chemical_name = ?\n"
                "quantity > ? AND status <> ?"
            ),
            "parameters": [requested_chemical, 0, "Expired"],
            "results": result.reset_index(drop=True),
            "warning": "",
        }
    if "sigma" in normalized and ("low" in normalized or "below" in normalized):
        result = frame[
            (frame["Manufacturer"] == "Sigma-Aldrich")
            & (frame["Quantity"] < 10)
            & (frame["Quantity"] > 0)
            & (frame["Status"] != "Expired")
        ]
        return {
            "route": "structured",
            "route_label": "Structured inventory query",
            "interpretation": "On-hand Sigma-Aldrich records below 10 units.",
            "query_code": (
                "Loaded inventory filter\n"
                "manufacturer = ? AND quantity < ?\n"
                "quantity > ? AND status <> ?"
            ),
            "parameters": ["Sigma-Aldrich", 10, 0, "Expired"],
            "results": result.reset_index(drop=True),
            "warning": "",
        }
    if "expir" in normalized and ("30" in normalized or "soon" in normalized):
        result = frame[
            frame["Expiry state"].isin(["Expiring soon", "Expired"])
        ]
        return {
            "route": "structured",
            "route_label": "Structured inventory query",
            "interpretation": "Records expired or expiring within 30 days.",
            "query_code": (
                "Loaded inventory filter\n"
                "expiry_state IN (?, ?)"
            ),
            "parameters": [],
            "results": result.reset_index(drop=True),
            "warning": "",
        }
    if "storage" in normalized and ("count" in normalized or "group" in normalized):
        return {
            "route": "structured",
            "route_label": "Structured inventory query",
            "interpretation": "Current inventory grouped by assigned storage location.",
            "query_code": (
                "Loaded inventory aggregation\n"
                "quantity > ? grouped by storage_location"
            ),
            "parameters": [0],
            "results": frame[frame["Quantity"] > 0].reset_index(drop=True),
            "warning": "",
        }
    return {
        "route": "unsupported",
        "route_label": "Needs clarification",
        "interpretation": (
            "The question could not be translated into an approved inventory filter."
        ),
        "query_code": "",
        "parameters": [],
        "results": empty,
        "warning": "Try a chemical name, expiry window, manufacturer, or chemistry concept.",
    }


def translate_chemical_query(query: str) -> dict[str, Any] | None:
    """Translate supported chemistry concepts into validated SMARTS templates."""
    normalized = query.lower().strip()
    if any(term in normalized for term in ("chiral", "asymmetric", "phosphine ligand")):
        return {
            "concept": "Chiral phosphine ligand",
            "patterns": ["[P;X3]([#6])([#6])[#6]"],
            "required_labels": ["Chiral ligand", "Phosphine ligand"],
            "explanation": (
                "Phosphine substructure match intersected with the cached chiral-ligand label."
            ),
        }
    if any(term in normalized for term in ("protic solvent", "protic")):
        return {
            "concept": "Protic solvent",
            "patterns": ["[O,S;H1]"],
            "required_labels": ["Protic solvent"],
            "explanation": "Heteroatom bearing an exchangeable hydrogen.",
        }
    if any(term in normalized for term in ("nitrile", "cyano")):
        return {
            "concept": "Nitrile-containing reagent",
            "patterns": ["[C]#[N]"],
            "required_labels": [],
            "explanation": "Carbon–nitrogen triple-bond substructure.",
        }
    if "lewis acid" in normalized:
        return {
            "concept": "Lewis acid",
            "patterns": ["[Ti]"],
            "required_labels": ["Lewis acid"],
            "explanation": "Validated structure match intersected with the CAS-level Lewis-acid label.",
        }
    if any(term in normalized for term in ("organometallic", "organolithium")):
        return {
            "concept": "Organometallic reagent",
            "patterns": ["[Li,Na,K,Mg,Zn,Cu,Ti,Fe]-[C]"],
            "required_labels": ["Organometallic"],
            "explanation": "Direct metal–carbon bond with a cached organometallic label.",
        }
    return None


def execute_smarts_query(
    frame: pd.DataFrame,
    patterns: list[str],
    required_labels: list[str],
) -> tuple[pd.DataFrame, int, str]:
    """Run RDKit substructure matching, then join only to usable inventory rows."""
    empty = empty_inventory_result(frame)
    if Chem is None:
        return empty, len(frame), "RDKit chemistry runtime is unavailable."
    query_molecules = [Chem.MolFromSmarts(pattern) for pattern in patterns]
    if not query_molecules or any(query is None for query in query_molecules):
        return empty, 0, "The translated SMARTS pattern failed validation."

    matched_indices: list[int] = []
    skipped = 0
    for index, row in frame.iterrows():
        smiles = str(row.get("SMILES", "")).strip()
        molecule = (
            Chem.MolFromSmiles(smiles)
            if smiles and smiles != "Not available"
            else None
        )
        if molecule is None:
            skipped += 1
            continue
        structure_matches = all(
            molecule.HasSubstructMatch(query_molecule)
            for query_molecule in query_molecules
        )
        label_text = str(row.get("Chemical labels", "")).lower()
        labels_match = all(label.lower() in label_text for label in required_labels)
        usable_inventory = row["Quantity"] > 0 and row["Status"] != "Expired"
        if structure_matches and labels_match and usable_inventory:
            matched_indices.append(index)

    result = frame.loc[matched_indices].copy().reset_index(drop=True)
    if not result.empty:
        pattern_text = " AND ".join(patterns)
        result["Match evidence"] = f"RDKit: {pattern_text}"
    return result, skipped, ""


def route_natural_language_query(
    query: str,
    frame: pd.DataFrame,
    *,
    provider_environment: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Route known intents first, then safely translate unfamiliar chemistry."""
    normalized = query.lower().strip()
    if not normalized:
        return compile_structured_query(query, frame)

    translation = translate_chemical_query(query)
    if translation:
        result, skipped, warning = execute_smarts_query(
            frame,
            translation["patterns"],
            translation["required_labels"],
        )
        return {
            "route": "chemical",
            "route_label": "Chemical meaning query",
            "interpretation": translation["concept"],
            "query_code": "\n".join(translation["patterns"]),
            "parameters": translation["required_labels"],
            "results": result,
            "warning": warning,
            "explanation": translation["explanation"],
            "skipped": skipped,
        }
    structured_plan = compile_structured_query(query, frame)
    if structured_plan["route"] != "unsupported":
        return structured_plan

    provider_result = translate_chemical_question(
        query,
        environ=provider_environment,
    )
    if provider_result.translation:
        translation = provider_result.translation
        result, skipped, warning = execute_smarts_query(
            frame,
            translation["patterns"],
            translation["required_labels"],
        )
        return {
            "route": "chemical",
            "route_label": "Chemical meaning query",
            "interpretation": translation["concept"],
            "query_code": "\n".join(translation["patterns"]),
            "parameters": translation["required_labels"],
            "results": result,
            "warning": warning,
            "explanation": translation["explanation"],
            "skipped": skipped,
        }
    return {
        "route": "unsupported",
        "route_label": "Chemistry translation unavailable",
        "interpretation": (
            "This question needs a reviewed SMARTS translation before search."
        ),
        "query_code": "",
        "parameters": [],
        "results": empty_inventory_result(frame),
        "warning": provider_result.message,
    }


def interpret_sample_query(
    query: str, frame: pd.DataFrame
) -> tuple[str, str, pd.DataFrame]:
    """Compatibility wrapper for the structured inventory query helper."""
    plan = compile_structured_query(query, frame)
    return plan["interpretation"], plan["query_code"], plan["results"]


def render_topbar() -> None:
    st.markdown(
        """
        <header class="topbar">
            <div class="brand">
                <div class="brand-mark">LM</div>
                <div>
                    <div class="brand-name">LabMind</div>
                    <div class="brand-subtitle">Reagent intelligence</div>
                </div>
            </div>
            <div class="topbar-note">
                <span class="topbar-note-dot"></span>
                Safety rules active
            </div>
        </header>
        """,
        unsafe_allow_html=True,
    )


def render_hero() -> None:
    st.markdown(
        """
        <section class="hero" aria-labelledby="labmind-hero-title">
            <div class="hero-copy-block">
                <div class="hero-kicker">Verified lab inventory</div>
                <h1 class="hero-title" id="labmind-hero-title">
                    Know what&rsquo;s in the lab.<br>
                    <span>Know why it belongs.</span>
                </h1>
                <p class="hero-copy">
                    Capture labels, classify chemistry, and search inventory with
                    evidence behind every answer.
                </p>
            </div>
            <div class="capability-rail" aria-label="LabMind capabilities">
                <div class="capability">
                    <span>01</span>
                    <strong>Capture the label</strong>
                    <small>Extracted fields stay editable</small>
                </div>
                <div class="capability">
                    <span>02</span>
                    <strong>Apply safety rules</strong>
                    <small>Storage decisions stay deterministic</small>
                </div>
                <div class="capability">
                    <span>03</span>
                    <strong>Verify inventory</strong>
                    <small>Structure and stock are both checked</small>
                </div>
            </div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def render_section_header(eyebrow: str, title: str, copy: str) -> None:
    section_id = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    with st.container(key=f"section_header_{section_id}"):
        st.markdown(
            f"""
            <div class="section-header">
                <div class="section-eyebrow">{escaped(eyebrow)}</div>
                <div class="section-title" id="{escaped(section_id)}"
                    role="heading" aria-level="2">{escaped(title)}</div>
                <p class="section-copy">{escaped(copy)}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_stepper() -> None:
    if st.session_state.get("add_confirmation"):
        active_step = 5
    elif st.session_state.get("add_extraction_complete"):
        active_step = {
            "Details": 2,
            "Order": 3,
            "Storage": 4,
            "Review": 5,
        }.get(st.session_state.get("add_stage"), 2)
    else:
        active_step = 1
    labels = [
        "Label",
        "Details",
        "Order",
        "Classify",
        "Review",
    ]
    items = []
    for index, label in enumerate(labels, start=1):
        state = "complete" if index < active_step else "active" if index == active_step else ""
        current = ' aria-current="step"' if index == active_step else ""
        items.append(
            f'<div class="step {state}" role="listitem"{current}>'
            f'<strong>0{index}</strong><span>{escaped(label)}</span></div>'
        )
    st.markdown(
        f'<div class="stepper" role="list" aria-label="Registration progress">'
        f'{"".join(items)}</div>',
        unsafe_allow_html=True,
    )


def initialize_extraction_state(contents: bytes, filename: str) -> None:
    """Populate editable label fields from a live provider or safe manual mode."""

    result = extract_label_fields(
        contents,
        filename,
        environ=streamlit_provider_environment(),
    )
    defaults = get_sample_extraction_result()
    for field, value in defaults.items():
        st.session_state.setdefault(f"add_field_{field}", value)
    for field, value in result.fields.items():
        state_key = f"add_field_{field}"
        if value not in ("", None) or state_key not in st.session_state:
            st.session_state[state_key] = value
    st.session_state["add_receipt_key"] = st.session_state.get(
        "add_receipt_key"
    ) or str(uuid4())
    st.session_state["add_extraction_notice"] = {
        "status": result.status,
        "message": result.message,
    }
    st.session_state["add_extraction_source"] = result.provider or "Manual entry"
    st.session_state["add_extraction_rationale"] = result.message
    st.session_state["add_extraction_complete"] = True
    st.session_state["add_confirmation"] = None
    st.session_state["add_stage"] = "Details"
    synchronize_classification_state()


def render_upload_step(*, compact: bool = False) -> bytes | None:
    upload_key = f"label_upload_{st.session_state.get('add_upload_nonce', 0)}"
    uploaded_file = st.session_state.get(upload_key)

    if uploaded_file is not None:
        contents = uploaded_file.getvalue()
        signature = uploaded_file_signature(contents)
        if st.session_state.get("add_file_signature") != signature:
            clear_state_keys(st.session_state)
            st.session_state["add_file_signature"] = signature
            st.session_state["add_upload_time"] = datetime.now().strftime("%H:%M")
        compact = compact and bool(
            st.session_state.get("add_extraction_complete")
        )

    if compact and uploaded_file is not None:
        uploaded_at = st.session_state.get("add_upload_time", "—")
        st.markdown(
            f"""
            <div class="compact-upload-header">
                <div class="section-eyebrow">Step 1 · Complete</div>
                <h2 class="compact-upload-title">Label captured</h2>
                <p class="compact-upload-file" title="{escaped(uploaded_file.name)}">
                    {escaped(uploaded_file.name)} · {format_file_size(len(contents))} · {uploaded_at}
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        with st.container(key="compact_label_preview"):
            st.image(uploaded_file, width="stretch")
        if st.button(
            "Re-extract label",
            type="primary",
            width="stretch",
            key="extract_label",
        ):
            initialize_extraction_state(contents, uploaded_file.name)
            st.rerun()
        with st.container(key="replace_label_image"):
            with st.expander("Replace label image"):
                st.file_uploader(
                    "Reagent label",
                    type=["png", "jpg", "jpeg", "webp"],
                    accept_multiple_files=False,
                    key=upload_key,
                    label_visibility="collapsed",
                )
        return contents

    render_section_header(
        "Step 1",
        "Add a reagent label",
        "Choose a clear photo of the bottle or package label.",
    )
    uploaded_file = st.file_uploader(
        "Reagent label",
        type=["png", "jpg", "jpeg", "webp"],
        accept_multiple_files=False,
        key=upload_key,
        label_visibility="collapsed",
    )
    if uploaded_file is None:
        st.markdown(
            '<p class="upload-hint" role="note">Use a straight-on, glare-free photo so every extracted field is easy to review.</p>',
            unsafe_allow_html=True,
        )
        return None

    contents = uploaded_file.getvalue()
    signature = uploaded_file_signature(contents)
    if st.session_state.get("add_file_signature") != signature:
        clear_state_keys(st.session_state)
        st.session_state["add_file_signature"] = signature
        st.session_state["add_upload_time"] = datetime.now().strftime("%H:%M")

    with st.container(key="label_preview"):
        st.image(uploaded_file, width="stretch")
    uploaded_at = st.session_state.get("add_upload_time", "—")
    st.markdown(
        f"""
        <div class="upload-meta">
            <div class="upload-meta-name">
                <span>Label image</span>
                <strong title="{escaped(uploaded_file.name)}">{escaped(uploaded_file.name)}</strong>
            </div>
            <div class="upload-meta-detail">
                {escaped(uploaded_file.type or "Image")} ·
                {format_file_size(len(contents))} · {uploaded_at}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    extract_label = (
        "Re-extract label"
        if st.session_state.get("add_extraction_complete")
        else "Extract label"
    )
    if st.button(
        extract_label,
        type="primary",
        width="stretch",
        key="extract_label",
    ):
        initialize_extraction_state(contents, uploaded_file.name)
        st.rerun()
    st.markdown(
        '<p class="quiet-note">Review every extracted field before continuing to order matching.</p>',
        unsafe_allow_html=True,
    )
    return contents


def render_extraction_step() -> None:
    if not st.session_state.get("add_extraction_complete"):
        return
    render_section_header(
        "Step 2",
        "Review label fields",
        "Confirm every value and complete anything the label image did not show.",
    )
    extraction_notice = st.session_state.get("add_extraction_notice")
    if extraction_notice:
        message = extraction_notice.get("message", "")
        if extraction_notice.get("status") == "failed":
            st.warning(message)
        elif extraction_notice.get("status") == "manual":
            st.info(message)
        elif extraction_notice.get("status") == "partial":
            st.warning(message)
        else:
            st.success(message)
    st.markdown(
        '<div class="status-line"><span class="status-dot"></span>Fields are editable and require review</div>',
        unsafe_allow_html=True,
    )
    left, right = st.columns(2, gap="small")
    with left:
        st.text_input("Chemical name", key="add_field_chemical_name")
        st.text_input("CAS number", key="add_field_cas_number")
        st.text_input("Specification", key="add_field_specification")
        st.text_input("Batch or lot number", key="add_field_batch_number")
    with right:
        st.text_input("Manufacturer", key="add_field_manufacturer")
        st.date_input("Expiry date", key="add_field_expiry_date")
        quantity_col, unit_col = st.columns([1.2, 1])
        with quantity_col:
            st.number_input(
                "Quantity",
                min_value=0.0,
                step=1.0,
                key="add_field_quantity",
            )
        with unit_col:
            st.selectbox(
                "Unit",
                ["mL", "L", "g", "kg", "mg", "units"],
                key="add_field_unit",
            )
        st.slider(
            "Recognition confidence",
            min_value=0,
            max_value=100,
            format="%d%%",
            key="add_field_confidence",
        )
    status_text, status_kind = cas_display_state(
        st.session_state.get("add_field_cas_number")
    )
    class_name = "status-line" if status_kind == "positive" else "status-line warning"
    st.markdown(
        f'<div class="{class_name}"><span class="status-dot"></span>{escaped(status_text)}</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<p class="quiet-note">Format guidance only. Final CAS verification remains part of the review process.</p>',
        unsafe_allow_html=True,
    )


def render_order_card(order: dict[str, Any], selected: bool = False) -> None:
    """Render a real pending-order candidate returned by the matching service."""

    selected_class = " selected" if selected else ""
    order_reference = str(order.get("order_reference") or order.get("order_id") or "Order")
    name = str(order.get("name") or order.get("chemical_name") or "Not recorded")
    cas_number = str(order.get("cas_number") or "Not recorded")
    manufacturer = str(order.get("manufacturer") or "Not recorded")
    quantity = f'{float(order.get("quantity") or 0):g} {order.get("quantity_unit") or order.get("unit") or "unit"}'
    raw_score = order.get("score")
    score = f"{float(raw_score):.0%}" if raw_score is not None else "Review"
    explanation = str(
        order.get("explanation")
        or "Match fields are evaluated deterministically against pending orders."
    )
    st.markdown(
        f"""
        <div class="order-card{selected_class}">
            <div class="order-id">{escaped(order_reference)} · {escaped(score)} match</div>
            <div class="order-name">{escaped(name)}</div>
            <div class="order-detail">
                CAS {escaped(cas_number)} · {escaped(manufacturer)} ·
                {escaped(quantity)}<br>{escaped(explanation)}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_pending_order_import() -> None:
    """Offer a deterministic CSV bridge while an ordering API is unavailable."""

    with st.expander("Import pending orders"):
        st.caption(
            "Upload a CSV exported from the order system. Required: "
            "order_reference (or order_id) and chemical_name (or name)."
        )
        uploaded_orders = st.file_uploader(
            "Pending-order CSV",
            type=["csv"],
            key="pending_order_csv",
            label_visibility="collapsed",
        )
        if uploaded_orders is None:
            return
        if st.button(
            "Import pending orders",
            width="stretch",
            key="import_pending_orders",
        ):
            try:
                frame = pd.read_csv(BytesIO(uploaded_orders.getvalue()))
                records = frame.where(pd.notna(frame), None).to_dict(orient="records")
                imported = import_pending_orders(
                    records,
                    source=f"CSV import: {uploaded_orders.name}",
                )
            except (ValueError, pd.errors.ParserError) as error:
                st.error(f"Could not import the order file: {error}")
                return
            st.success(f"Imported or updated {len(imported)} pending order(s).")
            clear_order_selection()
            st.rerun()


def _current_order_match_input() -> dict[str, Any]:
    return {
        "name": st.session_state.get("add_field_chemical_name", ""),
        "cas_number": st.session_state.get("add_field_cas_number", ""),
        "manufacturer": st.session_state.get("add_field_manufacturer", ""),
        "specification": st.session_state.get("add_field_specification", ""),
        "quantity": st.session_state.get("add_field_quantity", 0),
        "quantity_unit": st.session_state.get("add_field_unit", "unit"),
    }


def render_order_match_step() -> None:
    if not st.session_state.get("add_extraction_complete"):
        return
    render_section_header(
        "Step 3",
        "Connect the incoming order",
        "Matches are scored against actual pending orders. A low-confidence or "
        "ambiguous match always requires a person to choose.",
    )
    render_pending_order_import()

    match_input = _current_order_match_input()
    if not match_input["name"] or not validate_cas_number(match_input["cas_number"]):
        st.warning(
            "Enter a chemical name and a CAS number with a valid check digit "
            "before matching an incoming order."
        )
        st.checkbox(
            "Register without a linked order",
            key="add_register_without_order",
        )
        st.session_state.pop("add_selected_order", None)
        st.session_state.pop("add_order_match_score", None)
        return

    candidates = match_pending_orders(match_input)
    unique_match = select_unique_order_match(candidates)
    if unique_match:
        reference = str(unique_match["order_reference"])
        st.session_state["add_selected_order"] = reference
        st.session_state["add_order_match_score"] = float(unique_match["score"])
        st.session_state["add_register_without_order"] = False
        render_order_card(unique_match, selected=True)
        st.caption("Unique high-confidence match selected automatically.")
        return

    if not candidates:
        st.session_state.pop("add_selected_order", None)
        st.session_state.pop("add_order_match_score", None)
        st.info("No pending order currently matches these reviewed label details.")
        st.checkbox(
            "Register without a linked order",
            key="add_register_without_order",
        )
        return

    st.session_state["add_register_without_order"] = False
    options = {
        str(candidate["order_reference"]): candidate
        for candidate in candidates
    }
    selected_id = st.selectbox(
        "Select the matching order",
        list(options),
        format_func=lambda value: (
            f'{value} · {options[value].get("manufacturer") or "Not recorded"} '
            f'· {float(options[value].get("score") or 0):.0%}'
        ),
        key="add_selected_order",
    )
    selected = options[selected_id]
    st.session_state["add_order_match_score"] = float(selected["score"])
    render_order_card(selected, selected=True)
    with st.expander("Compare pending-order candidates"):
        comparison = pd.DataFrame(
            [
                {
                    "Order": candidate["order_reference"],
                    "Chemical": candidate.get("name"),
                    "Manufacturer": candidate.get("manufacturer"),
                    "Quantity": (
                        f'{float(candidate.get("quantity") or 0):g} '
                        f'{candidate.get("quantity_unit") or "unit"}'
                    ),
                    "Match": f'{float(candidate.get("score") or 0):.0%}',
                }
                for candidate in candidates
            ]
        )
        st.dataframe(comparison, hide_index=True, width="stretch")


def synchronize_classification_state(
    state: MutableMapping[str, Any] | None = None,
) -> dict[str, Any]:
    target = st.session_state if state is None else state
    cas_number = str(target.get("add_field_cas_number", "")).strip()
    if target.get("add_classification_cas") != cas_number:
        profile = get_chemical_classification(cas_number)
        decision = determine_storage_location(profile["constraints"])
        target["add_classification_cas"] = cas_number
        target["add_chemical_labels"] = list(profile["labels"])
        target["add_storage_constraints"] = list(profile["constraints"])
        target["add_classification_confidence"] = profile["confidence"]
        target["add_classification_source"] = profile["cache_status"]
        target["add_classification_rationale"] = profile["rationale"]
        target["add_storage_rule"] = decision["rule"]
        target["add_storage_location"] = decision["location"]
        target["add_storage_decision_signature"] = tuple(
            sorted(profile["constraints"])
        )
        target.pop("add_manual_storage_reviewed", None)
    return get_chemical_classification(cas_number)


def classify_current_chemical() -> None:
    """Run optional AI classification before storage widgets are instantiated."""

    result = classify_cas_with_gemini(
        st.session_state.get("add_field_cas_number", ""),
        chemical_name=st.session_state.get("add_field_chemical_name", ""),
        environ=streamlit_provider_environment(),
    )
    profile = result.classification
    current_labels = list(st.session_state.get("add_chemical_labels", []))
    current_constraints = list(st.session_state.get("add_storage_constraints", []))
    proposed_labels = list(profile.get("labels", []))
    proposed_constraints = list(profile.get("constraints", []))
    st.session_state["add_classification_cas"] = profile.get(
        "cas_number",
        st.session_state.get("add_field_cas_number", ""),
    )
    st.session_state["add_chemical_labels"] = list(
        dict.fromkeys(current_labels + proposed_labels)
    )
    st.session_state["add_storage_constraints"] = list(
        dict.fromkeys(current_constraints + proposed_constraints)
    )
    st.session_state["add_classification_confidence"] = profile.get(
        "confidence", 0
    )
    st.session_state["add_classification_source"] = profile.get(
        "cache_status", "Manual classification required"
    )
    st.session_state["add_classification_rationale"] = profile.get(
        "rationale", result.message
    )
    st.session_state["add_classification_notice"] = result.message
    st.session_state.pop("add_manual_storage_reviewed", None)


def render_storage_step() -> None:
    if not st.session_state.get("add_extraction_complete"):
        return
    classification = synchronize_classification_state()
    render_section_header(
        "Step 4",
        "Classify chemistry & assign storage",
        "Review the chemistry profile first. Hard safety rules determine the location.",
    )
    st.markdown(
        f"""
        <div class="safety-card">
            <div class="safety-kicker">Safety boundary</div>
            <div class="safety-title">AI describes chemistry. Rules assign storage.</div>
            <div class="order-detail">
                The chemistry layer may return multiple labels and constraints, but it
                cannot choose a cabinet or override segregation policy.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    chemistry_col, constraint_col = st.columns(2, gap="small")
    with chemistry_col:
        st.markdown("##### Chemical function labels")
        labels = st.multiselect(
            "Chemical function labels",
            CHEMICAL_LABEL_OPTIONS,
            key="add_chemical_labels",
            label_visibility="collapsed",
        )
        st.caption(
            f'{classification["cache_status"]} · '
            f'{st.session_state.get("add_classification_confidence", 0):.0%} confidence'
        )
    with constraint_col:
        st.markdown("##### Storage constraints")
        constraints = st.multiselect(
            "Storage constraints",
            STORAGE_CONSTRAINT_OPTIONS,
            key="add_storage_constraints",
            label_visibility="collapsed",
        )
        st.caption("Constraints are reviewed before the rule engine runs.")

    tags = "".join(
        f'<span class="tag">{escaped(tag)}</span>' for tag in labels
    )
    if tags:
        st.markdown(f'<div class="tag-row">{tags}</div>', unsafe_allow_html=True)
    st.markdown(
        f'<p class="quiet-note">{escaped(st.session_state.get("add_classification_rationale", ""))}</p>',
        unsafe_allow_html=True,
    )
    if not classification["labels"] and not classification["constraints"]:
        st.button(
            "Classify chemical function",
            width="stretch",
            key="run_chemical_classification",
            disabled=not validate_cas_number(
                st.session_state.get("add_field_cas_number", "")
            ),
            on_click=classify_current_chemical,
        )
    if st.session_state.get("add_classification_notice"):
        st.info(st.session_state["add_classification_notice"])

    decision = determine_storage_location(list(constraints))
    signature = tuple(sorted(constraints))
    if st.session_state.get("add_storage_decision_signature") != signature:
        st.session_state["add_storage_location"] = decision["location"]
        st.session_state["add_storage_decision_signature"] = signature
        st.session_state.pop("add_manual_storage_reviewed", None)
    st.session_state["add_storage_rule"] = decision["rule"]

    st.markdown(
        f"""
        <div class="decision-card">
            <div class="decision-route">Deterministic rule engine</div>
            <div class="decision-location">{escaped(decision["location"])}</div>
            <div class="order-detail">{escaped(decision["rule"])}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    selected_location = st.selectbox(
        "Final storage location",
        STORAGE_OPTIONS,
        key="add_storage_location",
    )
    review_required = (
        decision["location"] == "Manual Review Required"
        or selected_location != decision["location"]
    )
    if review_required:
        st.checkbox(
            "A laboratory safety reviewer approved this storage decision.",
            key="add_manual_storage_reviewed",
        )
    else:
        st.session_state["add_manual_storage_reviewed"] = True
    st.markdown(
        '<p class="quiet-note">The selected location is recorded with the triggered rule and reviewer state.</p>',
        unsafe_allow_html=True,
    )


def current_registration_payload() -> dict[str, Any]:
    selected_order = st.session_state.get("add_selected_order")
    if st.session_state.get("add_register_without_order"):
        selected_order = "Not linked"
    expiry = st.session_state.get("add_field_expiry_date")
    expiry_value = expiry.isoformat() if hasattr(expiry, "isoformat") else ""
    return {
        "chemical_name": st.session_state.get("add_field_chemical_name", ""),
        "cas_number": st.session_state.get("add_field_cas_number", ""),
        "specification": st.session_state.get("add_field_specification", ""),
        "batch_number": st.session_state.get("add_field_batch_number", ""),
        "manufacturer": st.session_state.get("add_field_manufacturer", ""),
        "expiry_date": expiry_value,
        "quantity": st.session_state.get("add_field_quantity", 0),
        "unit": st.session_state.get("add_field_unit", ""),
        "confidence": st.session_state.get("add_field_confidence", 0) / 100,
        "extraction_source": st.session_state.get(
            "add_extraction_source", "Manual entry"
        ),
        "extraction_rationale": st.session_state.get(
            "add_extraction_rationale", ""
        ),
        "pending_order": selected_order,
        "match_score": st.session_state.get("add_order_match_score"),
        "receipt_key": st.session_state.get("add_receipt_key", ""),
        "image_signature": st.session_state.get("add_file_signature", ""),
        "chemical_labels": list(st.session_state.get("add_chemical_labels", [])),
        "storage_constraints": list(
            st.session_state.get("add_storage_constraints", [])
        ),
        "classification_confidence": st.session_state.get(
            "add_classification_confidence", 0
        ),
        "classification_source": st.session_state.get(
            "add_classification_source", ""
        ),
        "classification_rationale": st.session_state.get(
            "add_classification_rationale", ""
        ),
        "storage_location": st.session_state.get("add_storage_location", ""),
        "storage_rule": st.session_state.get("add_storage_rule", ""),
        "storage_reviewed": bool(
            st.session_state.get("add_manual_storage_reviewed")
        ),
    }


def clear_order_selection() -> None:
    st.session_state.pop("add_selected_order", None)
    st.session_state.pop("add_order_match_score", None)
    st.session_state.pop("add_register_without_order", None)
    st.session_state.pop("add_confirmation", None)


def set_add_stage(stage: str) -> None:
    st.session_state["add_stage"] = stage


def render_stage_navigation(
    *,
    previous_stage: str | None = None,
    next_stage: str | None = None,
    next_label: str = "Continue",
    next_disabled: bool = False,
) -> None:
    if previous_stage and next_stage:
        previous_col, next_col = st.columns([1, 1])
        with previous_col:
            st.button(
                "Back",
                width="stretch",
                key=f"back_to_{previous_stage.lower()}",
                on_click=set_add_stage,
                args=(previous_stage,),
            )
        with next_col:
            st.button(
                next_label,
                type="primary",
                width="stretch",
                disabled=next_disabled,
                key=f"continue_to_{next_stage.lower()}",
                on_click=set_add_stage,
                args=(next_stage,),
            )
        return
    if next_stage:
        st.button(
            next_label,
            type="primary",
            width="stretch",
            disabled=next_disabled,
            key=f"continue_to_{next_stage.lower()}",
            on_click=set_add_stage,
            args=(next_stage,),
        )
        return
    if previous_stage:
        st.button(
            "Back",
            width="stretch",
            key=f"back_to_{previous_stage.lower()}",
            on_click=set_add_stage,
            args=(previous_stage,),
        )


def render_confirmation_step() -> None:
    if not st.session_state.get("add_extraction_complete"):
        return
    payload = current_registration_payload()
    confirmation = st.session_state.get("add_confirmation")
    if confirmation and confirmation.get("payload") != payload:
        st.session_state.pop("add_confirmation", None)
    render_section_header(
        "Step 5",
        "Confirm registration",
        "One final review before this record moves to the inventory workflow.",
    )
    identity_values = [
        ("Chemical", payload["chemical_name"]),
        ("CAS number", payload["cas_number"]),
        ("Batch", payload["batch_number"]),
        ("Manufacturer", payload["manufacturer"]),
        ("Quantity", f'{payload["quantity"]:g} {payload["unit"]}'),
        ("Pending order", payload["pending_order"] or "Selection required"),
    ]
    identity_summary = "".join(
        f"""
        <div class="summary-item">
            <div class="summary-label">{escaped(label)}</div>
            <div class="summary-value">{escaped(value)}</div>
        </div>
        """
        for label, value in identity_values
    )
    chemical_labels = payload["chemical_labels"] or ["Review required"]
    chemical_chips = "".join(
        f'<span class="summary-chip">{escaped(label)}</span>'
        for label in chemical_labels
    )
    storage_constraints = payload["storage_constraints"] or ["Review required"]
    constraint_chips = "".join(
        f'<span class="summary-chip constraint">{escaped(label)}</span>'
        for label in storage_constraints
    )
    storage_rule = payload["storage_rule"] or "No storage rule recorded."
    if " · " in storage_rule:
        storage_rule_code, storage_rule_copy = storage_rule.split(" · ", 1)
    else:
        storage_rule_code, storage_rule_copy = "Rule", storage_rule
    st.markdown(
        f"""
        <div class="review-summary">
            <section class="review-summary-group" aria-label="Record details">
                <div class="review-summary-heading">Record details</div>
                <div class="review-identity-grid">{identity_summary}</div>
            </section>
            <section class="review-summary-group" aria-label="Chemistry and safety">
                <div class="review-summary-heading">Chemistry &amp; safety</div>
                <div class="review-summary-stack">
                    <div class="summary-item">
                        <div class="summary-label">Chemical functions</div>
                        <div class="summary-chip-row">{chemical_chips}</div>
                    </div>
                    <div class="summary-item">
                        <div class="summary-label">Storage constraints</div>
                        <div class="summary-chip-row">{constraint_chips}</div>
                    </div>
                </div>
            </section>
            <section class="review-summary-group" aria-label="Storage decision">
                <div class="review-summary-heading">Storage decision</div>
                <div class="storage-location-card">
                    <div class="summary-label">Final location</div>
                    <div class="summary-value">{escaped(payload["storage_location"])}</div>
                </div>
                <div class="summary-item">
                    <div class="summary-label">Applied rule</div>
                    <div class="storage-rule">
                        <span class="storage-rule-code">{escaped(storage_rule_code)}</span>
                        <span class="storage-rule-copy">{escaped(storage_rule_copy)}</span>
                    </div>
                </div>
            </section>
        </div>
        """,
        unsafe_allow_html=True,
    )
    reviewed = st.checkbox(
        "I reviewed the extracted information.",
        key="add_reviewed",
    )
    order_ready = bool(
        payload["pending_order"]
        or st.session_state.get("add_register_without_order")
    )
    button_disabled = not (
        can_confirm_registration(
            reviewed, st.session_state.get("add_extraction_complete", False)
        )
        and order_ready
        and payload["storage_location"]
        and payload["storage_reviewed"]
        and validate_cas_number(payload["cas_number"])
    )
    if st.button(
        "Confirm registration",
        type="primary",
        width="stretch",
        disabled=button_disabled,
        key="confirm_registration",
    ):
        try:
            st.session_state["add_confirmation"] = confirm_sample_registration(
                payload,
                reviewed=reviewed,
            )
        except (ValueError, RuntimeError) as error:
            st.error(f"The record was not saved: {error}")

    confirmation = st.session_state.get("add_confirmation")
    if confirmation:
        if confirmation.get("classification_warning"):
            st.warning(
                "The reagent was registered, but its reusable CAS classification "
                f"cache could not be updated: {confirmation['classification_warning']}"
            )
        if confirmation.get("order_warning"):
            st.warning(
                "The reagent was registered, but its selected order could not be "
                f"marked received: {confirmation['order_warning']}"
            )
        st.markdown(
            f"""
            <div class="confirmation">
                <div class="confirmation-id">{escaped(confirmation["record_id"])}</div>
                <div class="confirmation-title">Registration recorded</div>
                <p class="section-copy">
                    The reviewed record is now available in Inventory search.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        with st.expander("Review prepared payload"):
            st.json(confirmation["payload"])

    st.button(
        "Reset workflow",
        width="stretch",
        key="reset_add",
        on_click=reset_add_workflow,
    )


def render_registration_workspace() -> None:
    st.session_state.setdefault("add_stage", "Details")
    stage = st.session_state["add_stage"]
    if stage == "Details":
        render_extraction_step()
        render_stage_navigation(next_stage="Order", next_label="Continue to order")
        return
    if stage == "Order":
        render_order_match_step()
        order_ready = bool(
            st.session_state.get("add_selected_order")
            or st.session_state.get("add_register_without_order")
        )
        render_stage_navigation(
            previous_stage="Details",
            next_stage="Storage",
            next_label="Continue to storage",
            next_disabled=not order_ready,
        )
        return
    if stage == "Storage":
        render_storage_step()
        render_stage_navigation(
            previous_stage="Order",
            next_stage="Review",
            next_label="Review registration",
            next_disabled=not bool(
                st.session_state.get("add_manual_storage_reviewed")
            ),
        )
        return
    render_confirmation_step()
    render_stage_navigation(previous_stage="Storage")


def render_add_tab() -> None:
    preserve_add_workflow_state()
    upload_key = f"label_upload_{st.session_state.get('add_upload_nonce', 0)}"
    has_upload = st.session_state.get(upload_key) is not None
    if not has_upload and st.session_state.get("add_file_signature"):
        clear_state_keys(st.session_state)

    render_section_header(
        "Reagent intake",
        "Register with confidence",
        "Move from a label photo to a reviewed storage decision without losing the evidence.",
    )
    render_stepper()

    if not has_upload:
        with st.container(key="intake_start"):
            with st.container(border=True, key="upload_panel"):
                render_upload_step(compact=False)
        return

    with st.container(key="intake_workspace"):
        left, right = st.columns([0.72, 1.28], gap="medium")
        with left:
            with st.container(border=True, key="upload_panel"):
                uploaded_contents = render_upload_step(
                    compact=bool(st.session_state.get("add_extraction_complete"))
                )
        with right:
            if uploaded_contents is None:
                return
            if not st.session_state.get("add_extraction_complete"):
                with st.container(border=True, key="review_placeholder"):
                    render_section_header(
                        "Ready to review",
                        "Extract five label fields",
                        "The extracted values stay editable before any inventory decision is prepared.",
                    )
                    st.markdown(
                        """
                        <div class="preview-list">
                            <div><span>01</span><strong>Chemical name</strong></div>
                            <div><span>02</span><strong>CAS number</strong></div>
                            <div><span>03</span><strong>Specification</strong></div>
                            <div><span>04</span><strong>Batch or lot</strong></div>
                            <div><span>05</span><strong>Manufacturer</strong></div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                return
            with st.container(border=True, key="registration_panel"):
                render_registration_workspace()


def render_inventory_metrics(frame: pd.DataFrame) -> None:
    manufacturer_count = int(frame["Manufacturer"].nunique()) if not frame.empty else 0
    attention_count = int(
        frame["Expiry state"].isin(["Expiring soon", "Expired"]).sum()
    )
    st.markdown(
        f"""
        <div class="metric-row">
            <div class="metric-card">
                <div class="metric-value">{len(frame)}</div>
                <div class="metric-label">Matched records</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{manufacturer_count}</div>
                <div class="metric-label">Manufacturers</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{attention_count}</div>
                <div class="metric-label">Expiry attention</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def set_primary_view(view: str) -> None:
    st.session_state["primary_view"] = view


def render_inventory_results(
    frame: pd.DataFrame,
    *,
    inventory_is_empty: bool = False,
) -> None:
    if frame.empty:
        if inventory_is_empty:
            title = "Your inventory is ready for its first record"
            copy = (
                "Register a reagent label to create a reviewable record, then return "
                "here to search it."
            )
        else:
            title = "No records match this search"
            copy = "Broaden the query or clear one or more filters and try again."
        st.markdown(
            f"""
            <div class="empty-state" role="status">
                <div class="empty-state-mark">00</div>
                <div class="empty-state-title">{escaped(title)}</div>
                <div class="empty-state-copy">{escaped(copy)}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if inventory_is_empty:
            st.button(
                "Register a reagent",
                key="empty_inventory_to_intake",
                on_click=set_primary_view,
                args=("Reagent intake",),
            )
        return

    render_inventory_metrics(frame)
    display_frame = frame.copy()
    display_frame["Expiry date"] = pd.to_datetime(display_frame["Expiry date"])
    display_columns = [
        "Record ID",
        "Chemical name",
        "CAS number",
        "Manufacturer",
        "Quantity",
        "Unit",
        "Status",
        "Expiry date",
        "Storage location",
    ]
    if "Match evidence" in display_frame.columns:
        display_columns.extend(["Chemical labels", "SMILES", "Match evidence"])
    display_columns = [
        column for column in display_columns if column in display_frame.columns
    ]
    st.dataframe(
        display_frame[display_columns],
        width="stretch",
        hide_index=True,
        column_config={
            "Expiry date": st.column_config.DateColumn("Expiry date", format="YYYY-MM-DD"),
            "Quantity": st.column_config.NumberColumn("Quantity", format="%d"),
        },
    )
    st.download_button(
        "Download CSV",
        data=frame.to_csv(index=False).encode("utf-8"),
        file_name="labmind-inventory-results.csv",
        mime="text/csv",
        width="stretch",
    )

    chart_choice = st.selectbox(
        "Visualize",
        [
            "Records by storage location",
            "Records by manufacturer",
            "Expiry status distribution",
        ],
        key="query_chart",
    )
    if chart_choice == "Records by storage location":
        chart_data = frame.groupby("Storage location").size().rename("Records")
    elif chart_choice == "Records by manufacturer":
        chart_data = frame.groupby("Manufacturer").size().rename("Records")
    else:
        chart_data = frame.groupby("Expiry state").size().rename("Records")
    st.bar_chart(chart_data, color="#0071e3")


def clear_query_state() -> None:
    keys = {
        "query_search",
        "query_manufacturer",
        "query_storage",
        "query_expiry",
        "query_minimum",
        "query_results",
        "query_natural_text",
        "query_natural_plan",
        "query_natural_plan_question",
    }
    clear_state_keys(st.session_state, frozenset(keys))


def render_basic_query(frame: pd.DataFrame) -> pd.DataFrame:
    search = st.text_input(
        "Search inventory",
        placeholder="Chemical, CAS number, batch, or record ID",
        key="query_search",
    )
    filter_cols = st.columns(4)
    with filter_cols[0]:
        manufacturer = st.selectbox(
            "Manufacturer",
            ["All manufacturers"] + sorted(frame["Manufacturer"].unique().tolist()),
            key="query_manufacturer",
        )
    with filter_cols[1]:
        storage = st.selectbox(
            "Storage",
            ["All locations"] + sorted(frame["Storage location"].unique().tolist()),
            key="query_storage",
        )
    with filter_cols[2]:
        expiry = st.selectbox(
            "Expiry state",
            ["All expiry states", "Current", "Expiring soon", "Expired"],
            key="query_expiry",
        )
    with filter_cols[3]:
        minimum = st.number_input(
            "Minimum quantity",
            min_value=0,
            step=1,
            key="query_minimum",
        )
    search_col, clear_col = st.columns([1, 1])
    with search_col:
        search_clicked = st.button(
            "Search inventory",
            type="primary",
            width="stretch",
            key="run_basic_query",
        )
    with clear_col:
        st.button(
            "Clear filters",
            width="stretch",
            key="clear_basic_query",
            on_click=clear_query_state,
            disabled=not bool(
                search.strip()
                or manufacturer != "All manufacturers"
                or storage != "All locations"
                or expiry != "All expiry states"
                or minimum > 0
            ),
        )
    if search_clicked or "query_results" not in st.session_state:
        st.session_state["query_results"] = filter_sample_inventory(
            frame,
            search_text=search,
            manufacturer=manufacturer,
            storage_location=storage,
            expiry_state=expiry,
            minimum_quantity=int(minimum),
        )
    return st.session_state["query_results"]


def set_natural_query_example(question: str) -> None:
    st.session_state["query_natural_text"] = question
    st.session_state.pop("query_natural_plan", None)


def apply_natural_query_example(examples: dict[str, str]) -> None:
    selection = st.session_state.get("query_example_choice")
    if selection in examples:
        set_natural_query_example(examples[selection])


def render_natural_language_query(frame: pd.DataFrame) -> pd.DataFrame:
    query_text = st.text_area(
        "Ask about inventory",
        placeholder=(
            "Try “Do we have a chiral phosphine ligand for asymmetric reduction?”"
        ),
        height=110,
        key="query_natural_text",
    )
    examples = {
        "Chiral ligands": (
            "Do we have a chiral phosphine ligand for asymmetric reduction?"
        ),
        "Protic solvents": "Which protic solvents are currently on hand?",
        "Expiry check": "Show reagents expiring within 30 days.",
    }
    st.pills(
        "Suggested questions",
        list(examples),
        key="query_example_choice",
        width="stretch",
        label_visibility="collapsed",
        on_change=apply_natural_query_example,
        args=(examples,),
    )
    if st.button(
        "Run verified search",
        type="primary",
        width="stretch",
        key="run_natural_query",
        disabled=not query_text.strip(),
    ):
        submitted_question = st.session_state.get("query_natural_text", "").strip()
        st.session_state["query_natural_plan"] = route_natural_language_query(
            submitted_question,
            frame,
            provider_environment=streamlit_provider_environment(),
        )
        st.session_state["query_natural_plan_question"] = submitted_question

    with st.expander("How answers are verified"):
        st.markdown(
            """
            <div class="verification-boundary">
                <strong>Meaning is interpreted. Availability comes from inventory.</strong>
                <span>
                    Structured questions become bound filters. Chemistry questions become
                    validated SMARTS, run through RDKit, then join back to on-hand records.
                </span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    plan = st.session_state.get("query_natural_plan")
    plan_matches_question = (
        st.session_state.get("query_natural_plan_question") == query_text.strip()
    )
    if not plan or not plan_matches_question:
        st.markdown(
            '<div class="query-ready">Ask a question to see the verified execution path and matching inventory records.</div>',
            unsafe_allow_html=True,
        )
        return empty_inventory_result(frame)

    st.markdown(
        f"""
        <div class="order-card selected">
            <div class="query-route">{escaped(plan["route_label"])}</div>
            <div class="order-name">{escaped(plan["interpretation"])}</div>
            <div class="order-detail">
                {escaped(plan.get("explanation", "An allowlisted plan is executed against the loaded inventory."))}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if plan["route"] == "chemical":
        trace = [
            ("01 · Interpret", "Chemical concept"),
            ("02 · Validate", "SMARTS pattern"),
            ("03 · Match", "RDKit structures"),
            ("04 · Verify", "On-hand inventory join"),
        ]
    elif plan["route"] == "structured":
        trace = [
            ("01 · Interpret", "Inventory intent"),
            ("02 · Compile", "Approved record filter"),
            ("03 · Apply", "Loaded inventory records"),
            ("04 · Return", "Verified record state"),
        ]
    else:
        trace = [
            ("01 · Inspect", "Question received"),
            ("02 · Stop safely", "No approved translation"),
        ]
    trace_html = "".join(
        f'<div class="trace-step"><strong>{escaped(title)}</strong>{escaped(copy)}</div>'
        for title, copy in trace
    )
    st.markdown(
        f'<div class="query-trace">{trace_html}</div>',
        unsafe_allow_html=True,
    )
    if plan["query_code"]:
        st.code(plan["query_code"])
    if plan.get("parameters"):
        st.caption(
            "Bound parameters / required labels: "
            + " · ".join(str(value) for value in plan["parameters"])
        )
    if plan.get("warning"):
        st.warning(plan["warning"])
    if plan["route"] == "chemical" and not plan.get("warning"):
        match_count = len(plan["results"])
        skipped_count = int(plan.get("skipped", 0))
        match_label = "match" if match_count == 1 else "matches"
        skipped_label = "record" if skipped_count == 1 else "records"
        message = (
            f"{match_count} verified on-hand {match_label} · "
            f"{skipped_count} structure {skipped_label} skipped"
        )
        if match_count:
            st.success(message)
        else:
            st.markdown(
                f'<div class="status-line neutral" role="status">'
                f'<span class="status-dot"></span>{escaped(message)}</div>',
                unsafe_allow_html=True,
            )
    return plan["results"]


def render_query_tab() -> None:
    frame = load_sample_inventory()
    render_section_header(
        "Inventory",
        "Find what the lab has on hand",
        "Search by precise filters or describe what you are looking for.",
    )
    mode = st.segmented_control(
        "Query mode",
        ["Basic filters", "Natural-language query"],
        key="query_mode",
        default="Basic filters",
        required=True,
        width="stretch",
        label_visibility="collapsed",
    )
    with st.container(border=True, key="query_panel"):
        if mode == "Basic filters":
            results = render_basic_query(frame)
        else:
            results = render_natural_language_query(frame)
    if mode == "Basic filters" or st.session_state.get("query_natural_plan"):
        render_inventory_results(results, inventory_is_empty=frame.empty)
    st.markdown(
        '<p class="quiet-note">Every answer is derived from the loaded inventory records; the language layer never invents stock state.</p>',
        unsafe_allow_html=True,
    )


def main() -> None:
    st.set_page_config(
        page_title="LabMind — Verified Reagent Intelligence",
        page_icon="🧪",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    apply_theme()
    render_topbar()
    render_hero()
    primary_view = st.segmented_control(
        "Workspace",
        ["Reagent intake", "Inventory search"],
        key="primary_view",
        default="Reagent intake",
        required=True,
        width="stretch",
        label_visibility="collapsed",
    )
    with st.container(key="workspace_shell"):
        if primary_view == "Reagent intake":
            render_add_tab()
        else:
            render_query_tab()


if __name__ == "__main__":
    main()
