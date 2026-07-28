from __future__ import annotations

import hashlib
import html
import json
from datetime import date, datetime, timedelta
from typing import Any, MutableMapping

import pandas as pd
import streamlit as st

try:
    from rdkit import Chem
except ImportError:  # The UI fails closed until the chemistry runtime is installed.
    Chem = None


ADD_STATE_KEYS = {
    "add_file_signature",
    "add_upload_time",
    "add_stage",
    "add_extraction_complete",
    "add_confirmation",
    "add_order_scenario",
    "add_selected_order",
    "add_register_without_order",
    "add_storage_location",
    "add_classification_cas",
    "add_chemical_labels",
    "add_storage_constraints",
    "add_classification_confidence",
    "add_classification_source",
    "add_classification_rationale",
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

CHEMICAL_CLASSIFICATION_PROFILES = {
    "64-17-5": {
        "labels": ["Flammable liquid", "Protic solvent", "Organic compound"],
        "constraints": [
            "Flammable",
            "Keep away from oxidizers",
            "Ambient temperature",
        ],
        "confidence": 0.97,
        "rationale": "A volatile protic solvent with a low flash point.",
    },
    "7550-45-0": {
        "labels": ["Lewis acid", "Inorganic compound", "Moisture reactive"],
        "constraints": ["Corrosive", "Water reactive", "Segregate from bases"],
        "confidence": 0.94,
        "rationale": "A strong Lewis acid that reacts vigorously with moisture.",
    },
    "109-72-8": {
        "labels": ["Organometallic", "Pyrophoric", "Reducing agent"],
        "constraints": [
            "Flammable",
            "Water reactive",
            "Keep away from acids",
            "Locked storage",
        ],
        "confidence": 0.96,
        "rationale": "An organolithium reagent requiring inert, tightly controlled storage.",
    },
    "76189-55-4": {
        "labels": [
            "Chiral ligand",
            "Phosphine ligand",
            "Organophosphorus compound",
        ],
        "constraints": ["Ambient temperature", "Keep away from oxidizers"],
        "confidence": 0.93,
        "rationale": "A privileged chiral bisphosphine ligand used in asymmetric catalysis.",
    },
    "210169-54-3": {
        "labels": [
            "Chiral ligand",
            "Phosphine ligand",
            "Organophosphorus compound",
        ],
        "constraints": ["Ambient temperature", "Keep away from oxidizers"],
        "confidence": 0.91,
        "rationale": "A chiral bisphosphine ligand commonly used for asymmetric transformations.",
    },
}


def apply_theme() -> None:
    st.markdown(
        """
        <style>
        :root {
            --canvas: #f5f5f7;
            --surface: rgba(255, 255, 255, 0.94);
            --surface-strong: #ffffff;
            --ink: #1d1d1f;
            --secondary: #6e6e73;
            --tertiary: #86868b;
            --line: rgba(0, 0, 0, 0.075);
            --line-strong: rgba(0, 0, 0, 0.13);
            --accent: #0071e3;
            --accent-hover: #0068d1;
            --teal: #087f75;
            --green: #1f7535;
            --amber: #a95d00;
            --red: #d70015;
            --shadow: 0 18px 55px rgba(0, 0, 0, 0.065);
            --radius-card: 28px;
            --radius-control: 14px;
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
                radial-gradient(circle at 50% -180px, #ffffff 0, #f5f5f7 510px),
                var(--canvas);
            color: var(--ink);
        }

        div.block-container {
            max-width: 1180px;
            padding: 1rem 2rem 5rem;
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
            min-height: 54px;
            padding: 0 2px 12px;
        }

        .brand {
            align-items: center;
            display: flex;
            gap: 11px;
        }

        .brand-mark {
            align-items: center;
            background: var(--ink);
            border-radius: 10px;
            color: #fff;
            display: inline-flex;
            font-size: 13px;
            font-weight: 760;
            height: 34px;
            justify-content: center;
            letter-spacing: -0.02em;
            width: 34px;
        }

        .brand-name {
            color: var(--ink);
            font-size: 17px;
            font-weight: 700;
            line-height: 1.1;
        }

        .brand-subtitle {
            color: var(--secondary);
            font-size: 12px;
            margin-top: 3px;
        }

        .topbar-note {
            align-items: center;
            color: var(--secondary);
            display: flex;
            font-size: 12px;
            font-weight: 560;
            gap: 7px;
        }

        .topbar-note-dot {
            background: var(--green);
            border-radius: 999px;
            box-shadow: 0 0 0 4px rgba(31, 117, 53, 0.10);
            height: 7px;
            width: 7px;
        }

        .hero {
            align-items: center;
            display: flex;
            flex-direction: column;
            padding: 46px 0 30px;
            text-align: center;
        }

        .hero-kicker {
            color: var(--accent);
            font-size: 14px;
            font-weight: 680;
            letter-spacing: -0.01em;
            margin-bottom: 14px;
        }

        .hero-title {
            color: var(--ink);
            font-size: clamp(44px, 5.5vw, 68px);
            font-weight: 720;
            letter-spacing: -0.06em;
            line-height: 0.99;
            margin: 0;
            max-width: 980px;
        }

        .hero-title span {
            color: var(--secondary);
        }

        .hero-copy {
            color: var(--secondary);
            font-size: 18px;
            letter-spacing: -0.01em;
            line-height: 1.5;
            margin: 20px auto 0;
            max-width: 730px;
        }

        .capability-rail {
            align-items: stretch;
            background: rgba(255, 255, 255, 0.72);
            border: 1px solid var(--line);
            border-radius: 20px;
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            margin-top: 24px;
            max-width: 840px;
            padding: 5px;
            width: 100%;
        }

        .capability {
            display: grid;
            gap: 2px;
            grid-template-columns: 26px 1fr;
            padding: 12px 18px;
            text-align: left;
        }

        .capability + .capability {
            border-left: 1px solid var(--line);
        }

        .capability > span {
            color: var(--accent);
            font-size: 10px;
            font-weight: 720;
            grid-row: 1 / 3;
            letter-spacing: 0.04em;
            padding-top: 2px;
        }

        .capability strong {
            color: var(--ink);
            font-size: 13px;
            font-weight: 660;
        }

        .capability small {
            color: var(--secondary);
            font-size: 11px;
            line-height: 1.35;
        }

        .section-header {
            margin: 0;
        }

        .section-eyebrow {
            color: var(--secondary);
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 0.09em;
            margin-bottom: 7px;
            text-transform: uppercase;
        }

        .section-title {
            color: var(--ink);
            font-size: clamp(26px, 2.5vw, 34px);
            font-weight: 690;
            letter-spacing: -0.045em;
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
            gap: 12px;
            grid-template-columns: repeat(5, 1fr);
            margin: 0 0 var(--space-1);
        }

        .step {
            background: transparent;
            border: 0;
            border-radius: 0;
            color: var(--tertiary);
            font-size: 12px;
            overflow: hidden;
            padding: 13px 2px 0;
            position: relative;
            text-align: left;
            text-overflow: ellipsis;
            white-space: nowrap;
        }

        .step::before {
            background: rgba(0, 0, 0, 0.10);
            border-radius: 999px;
            content: "";
            height: 3px;
            left: 0;
            position: absolute;
            right: 0;
            top: 0;
        }

        .step strong {
            color: inherit;
            display: inline;
            font-size: 11px;
            font-weight: 680;
            margin-right: 6px;
        }

        .step.active {
            background: transparent;
            color: var(--ink);
            font-weight: 650;
        }

        .step.active::before {
            background: var(--accent);
        }

        .step.complete {
            background: transparent;
            color: #515154;
        }

        .step.complete::before {
            background: var(--ink);
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
            overflow: hidden;
        }

        .st-key-upload_panel > div,
        .st-key-review_placeholder > div,
        .st-key-registration_panel > div,
        .st-key-query_panel > div {
            padding: var(--space-4);
        }

        div[data-testid="stFileUploader"] section {
            background: rgba(245, 245, 247, 0.72);
            border: 1px dashed var(--line-strong);
            border-radius: var(--radius-control);
            min-height: 142px;
            padding: var(--space-4);
            transition: border-color .18s ease, background .18s ease,
                transform .18s ease;
        }

        div[data-testid="stFileUploader"] section:hover {
            background: #fff;
            border-color: var(--accent);
            transform: translateY(-1px);
        }

        div[data-testid="stFileUploader"] button,
        div.stButton > button,
        div[data-testid="stDownloadButton"] > button {
            border-radius: 999px;
            font-weight: 600;
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
            background: #f5f5f7 !important;
            border: 1px solid #d2d2d7 !important;
            border-radius: 12px !important;
            box-shadow: none !important;
            min-height: 44px;
            transition: background-color .16s ease, border-color .16s ease,
                box-shadow .16s ease;
        }

        div[data-testid="stTextInputRootElement"]:focus-within,
        div[data-testid="stNumberInputContainer"]:focus-within,
        div[data-testid="stSelectbox"] [role="group"]:focus-within,
        div[data-testid="stDateInput"] [data-baseweb="input"]:focus-within {
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

        div[data-testid="stExpander"] summary,
        div[data-testid="stExpander"] summary p,
        div[data-testid="stExpander"] summary span {
            color: var(--ink) !important;
        }

        .empty-state {
            align-items: center;
            background: rgba(245, 245, 247, 0.72);
            border: 1px solid var(--line);
            border-radius: var(--radius-control);
            color: var(--secondary);
            display: flex;
            justify-content: center;
            min-height: 112px;
            padding: var(--space-4);
            text-align: center;
        }

        .upload-hint {
            color: var(--tertiary);
            font-size: 12px;
            line-height: 1.5;
            margin: 12px 2px 0;
            text-align: center;
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
            gap: 7px;
            padding: 13px 14px;
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
            gap: 10px;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            margin-top: 13px;
        }

        .meta-item, .summary-item {
            background: rgba(245, 245, 247, 0.72);
            border-radius: 13px;
            padding: 12px 13px;
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
            margin: 4px 0 16px;
            padding: 11px 13px;
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
            border-radius: 16px;
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
            color: var(--tertiary);
            font-size: 12px;
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
            backdrop-filter: saturate(180%) blur(18px);
            background: rgba(245, 245, 247, 0.92);
            margin: 0 0 var(--space-6);
            max-width: none;
            padding: 6px 0;
            position: sticky;
            top: 0;
            z-index: 30;
        }

        .st-key-primary_view div[data-testid="stButtonGroup"],
        .st-key-primary_view div[data-testid="stSegmentedControl"] {
            margin: 0;
            overflow: visible;
            padding: 0;
        }

        .st-key-primary_view [role="radiogroup"],
        .st-key-primary_view div[data-testid="stSegmentedControl"] > div {
            backdrop-filter: saturate(180%) blur(18px);
            background: rgba(232, 232, 237, 0.88);
            border: 1px solid rgba(0, 0, 0, 0.08);
            border-radius: 17px;
            box-shadow: 0 8px 26px rgba(0, 0, 0, 0.10);
            display: flex;
            margin: 0 auto;
            max-width: 680px;
            min-width: 0;
            padding: 5px;
            width: 100%;
        }

        .st-key-primary_view button[data-variant="segmented_control"],
        .st-key-primary_view div[data-testid="stSegmentedControl"] button {
            border: 1px solid transparent !important;
            flex: 1 1 50%;
            font-size: 14px;
            font-weight: 640;
            height: 48px !important;
            min-height: 48px !important;
            min-width: 0;
        }

        .st-key-primary_view button[data-variant="segmented_control"][data-selected],
        .st-key-primary_view button[data-variant="segmented_control"][aria-checked="true"],
        .st-key-primary_view div[data-testid="stSegmentedControl"] button[aria-pressed="true"] {
            border-color: transparent !important;
            box-shadow: 0 2px 7px rgba(0, 0, 0, 0.13) !important;
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
            top: 88px;
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
            align-items: center;
            background: rgba(245, 245, 247, 0.78);
            border: 1px solid var(--line);
            border-radius: var(--radius-control);
            color: var(--secondary);
            display: flex;
            font-size: 14px;
            justify-content: center;
            min-height: 88px;
            padding: var(--space-4);
            text-align: center;
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
            gap: var(--space-2);
            grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
            margin-top: var(--space-3);
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
                padding: 34px 0 24px;
            }

            .hero-title {
                font-size: clamp(36px, 10.3vw, 44px);
            }

            .hero-copy {
                font-size: 16px;
                margin-top: 16px;
            }

            .capability-rail {
                background: transparent;
                border: 0;
                border-radius: 0;
                display: flex;
                gap: var(--space-1);
                margin-top: var(--space-4);
                overflow-x: auto;
                padding: 2px 2px 8px;
                scroll-snap-type: x proximity;
            }

            .capability {
                background: rgba(255, 255, 255, 0.84);
                border: 1px solid var(--line) !important;
                border-radius: 16px;
                flex: 0 0 220px;
                padding: 13px 15px;
                scroll-snap-align: start;
            }

            .st-key-primary_view {
                margin-bottom: var(--space-6);
                top: 8px;
            }

            .st-key-primary_view button[data-variant="segmented_control"],
            .st-key-primary_view div[data-testid="stSegmentedControl"] button {
                font-size: 13px;
                height: 48px !important;
                min-height: 48px !important;
            }

            .stepper {
                display: grid;
                gap: 8px;
                grid-template-columns: repeat(5, minmax(0, 1fr));
                margin-top: 8px;
                overflow: visible;
                padding-bottom: 4px;
            }

            .step {
                font-size: 0;
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

            .st-key-upload_panel > div,
            .st-key-review_placeholder > div,
            .st-key-registration_panel > div,
            .st-key-query_panel > div {
                padding: 20px;
            }
        }

        @media (max-width: 460px) {
            .topbar-note {
                display: none;
            }

            .capability-rail {
                display: none;
            }

            .hero {
                align-items: flex-start;
                text-align: left;
            }

            .hero-copy {
                margin-left: 0;
            }

            .section-title {
                font-size: 28px;
            }

            .st-key-primary_view button[data-variant="segmented_control"],
            .st-key-primary_view div[data-testid="stSegmentedControl"] button {
                padding-left: 8px !important;
                padding-right: 8px !important;
            }

            .metric-row {
                grid-template-columns: repeat(2, minmax(0, 1fr));
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
    """Temporary UI data. TODO: replace with vision_extract output."""
    return {
        "chemical_name": "Ethanol",
        "cas_number": "64-17-5",
        "specification": "HPLC grade",
        "batch_number": "SHBJ3763",
        "manufacturer": "Sigma-Aldrich",
        "expiry_date": date(2027, 4, 30),
        "quantity": 500.0,
        "unit": "mL",
        "confidence": 92,
    }


def get_sample_order_matches(scenario: str) -> list[dict[str, Any]]:
    """Temporary UI data. TODO: replace with order_matcher output."""
    orders = [
        {
            "order_id": "PO-2026-1842",
            "chemical_name": "Ethanol",
            "cas_number": "64-17-5",
            "manufacturer": "Sigma-Aldrich",
            "quantity": "500 mL",
            "score": "98%",
            "explanation": "CAS number, manufacturer, grade, and quantity align.",
        },
        {
            "order_id": "PO-2026-1798",
            "chemical_name": "Ethanol",
            "cas_number": "64-17-5",
            "manufacturer": "Fisher Chemical",
            "quantity": "1 L",
            "score": "81%",
            "explanation": "Chemical and CAS number align; manufacturer and quantity differ.",
        },
        {
            "order_id": "PO-2026-1771",
            "chemical_name": "Ethyl alcohol",
            "cas_number": "64-17-5",
            "manufacturer": "Sigma-Aldrich",
            "quantity": "1 L",
            "score": "88%",
            "explanation": "CAS number and manufacturer align; order uses an alternate name.",
        },
    ]
    if scenario == "Unique match":
        return orders[:1]
    if scenario == "Multiple matches":
        return orders
    return []


def get_chemical_classification(cas_number: str | None) -> dict[str, Any]:
    """Return a CAS-level chemistry profile from the local classification cache."""
    normalized = (cas_number or "").strip()
    profile = CHEMICAL_CLASSIFICATION_PROFILES.get(normalized)
    if profile:
        return {
            **profile,
            "labels": list(profile["labels"]),
            "constraints": list(profile["constraints"]),
            "cas_number": normalized,
            "cache_status": "CAS classification cache",
        }
    return {
        "cas_number": normalized,
        "labels": [],
        "constraints": [],
        "confidence": 0.0,
        "rationale": "No cached profile is available. A chemistry review is required.",
        "cache_status": "Review required",
    }


def determine_storage_location(constraints: list[str]) -> dict[str, str]:
    """Apply hard storage rules; model classifications never select a cabinet."""
    constraint_set = set(constraints)
    supported = set(STORAGE_CONSTRAINT_OPTIONS)
    conflicting = (
        {"Refrigerated", "Flammable"} <= constraint_set
        or {"Corrosive", "Flammable"} <= constraint_set
    )
    if (
        not constraint_set
        or not constraint_set <= supported
        or conflicting
        or "Water reactive" in constraint_set
        or "Locked storage" in constraint_set
    ):
        return {
            "location": "Manual Review Required",
            "rule": "SR-01 · Unknown, conflicting, reactive, or restricted constraints require safety review.",
        }
    if "Refrigerated" in constraint_set:
        return {
            "location": "Refrigerated Storage",
            "rule": "SR-02 · Refrigerated materials remain in temperature-controlled storage.",
        }
    if "Corrosive" in constraint_set:
        return {
            "location": "Corrosives Cabinet",
            "rule": "SR-03 · Corrosives are segregated from general and flammable stock.",
        }
    if "Flammable" in constraint_set:
        return {
            "location": "Flammable Cabinet B",
            "rule": "SR-04 · Flammable liquids are assigned to an approved cabinet.",
        }
    return {
        "location": "General Shelf A",
        "rule": "SR-05 · Ambient material with no special segregation rule.",
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
    payload: dict[str, Any], *, reviewed: bool
) -> dict[str, Any]:
    """Temporary UI response. TODO: replace with db_utils.insert_reagent."""
    if not reviewed:
        raise ValueError("Registration requires reviewed information.")
    return {
        "record_id": "LAB-2026-001",
        "prepared_at": datetime.now().isoformat(timespec="seconds"),
        "payload": payload,
    }


def clear_state_keys(
    state: MutableMapping[str, Any],
    keys: set[str] | frozenset[str] = frozenset(ADD_STATE_KEYS),
) -> None:
    for key in keys:
        state.pop(key, None)


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


def load_sample_inventory(today: date | None = None) -> pd.DataFrame:
    """Return deterministic UI records. TODO: replace with inventory repository."""
    today = today or date.today()
    records = [
        ("LAB-001", "Ethanol", "64-17-5", "Sigma-Aldrich", "SHBJ3763", "HPLC grade", 8, "500 mL", today + timedelta(days=19), "Flammable Cabinet B"),
        ("LAB-002", "Methanol", "67-56-1", "Fisher Chemical", "M240912", "ACS grade", 24, "1 L", today + timedelta(days=132), "Flammable Cabinet A"),
        ("LAB-003", "Acetonitrile", "75-05-8", "Sigma-Aldrich", "STBH1142", "LC-MS grade", 4, "1 L", today + timedelta(days=7), "Flammable Cabinet B"),
        ("LAB-004", "Hydrochloric acid", "7647-01-0", "VWR Chemicals", "HCL-5521", "37%", 13, "500 mL", today + timedelta(days=280), "Corrosives Cabinet"),
        ("LAB-005", "Sodium chloride", "7647-14-5", "Sigma-Aldrich", "SLCH0087", "BioUltra", 42, "500 g", today + timedelta(days=540), "General Shelf A"),
        ("LAB-006", "Acetic acid", "64-19-7", "Fisher Chemical", "A24-887", "Glacial", 6, "500 mL", today - timedelta(days=3), "Corrosives Cabinet"),
        ("LAB-007", "Phosphate-buffered saline", "—", "Thermo Fisher", "PBS-1094", "10×", 18, "500 mL", today + timedelta(days=46), "Refrigerated Storage"),
        ("LAB-008", "Dimethyl sulfoxide", "67-68-5", "Sigma-Aldrich", "MKCL3021", "Molecular biology", 5, "100 mL", today + timedelta(days=365), "General Shelf B"),
        ("LAB-009", "Trypsin-EDTA", "—", "Gibco", "T2026-14", "0.25%", 7, "100 mL", today + timedelta(days=12), "Freezer Storage"),
        ("LAB-010", "Tris base", "77-86-1", "Bio-Rad", "TRS-7730", "Molecular biology", 31, "1 kg", today + timedelta(days=700), "General Shelf A"),
        ("LAB-011", "Titanium tetrachloride", "7550-45-0", "Sigma-Aldrich", "TI-4421", "99.9%", 2, "100 mL", today + timedelta(days=410), "Corrosives Cabinet"),
        ("LAB-012", "n-Butyllithium", "109-72-8", "Acros Organics", "BL-9031", "2.5 M in hexanes", 1, "100 mL", today + timedelta(days=82), "Manual Review Required"),
        ("LAB-013", "(R)-BINAP", "76189-55-4", "Strem Chemicals", "BN-1184", "98%", 3, "5 g", today + timedelta(days=620), "General Shelf B"),
        ("LAB-014", "(S)-SEGPHOS", "210169-54-3", "TCI America", "SG-2407", "98%", 2, "1 g", today + timedelta(days=480), "General Shelf B"),
    ]
    frame = pd.DataFrame(
        records,
        columns=[
            "Record ID",
            "Chemical name",
            "CAS number",
            "Manufacturer",
            "Batch number",
            "Specification",
            "Quantity",
            "Unit",
            "Expiry date",
            "Storage location",
        ],
    )
    chemistry_metadata = {
        "64-17-5": (
            "CCO",
            "Flammable liquid · Protic solvent · Organic compound",
            "Flammable · Keep away from oxidizers",
        ),
        "67-56-1": (
            "CO",
            "Flammable liquid · Protic solvent · Organic compound",
            "Flammable · Toxic",
        ),
        "75-05-8": (
            "CC#N",
            "Flammable liquid · Polar aprotic solvent",
            "Flammable · Toxic",
        ),
        "7647-01-0": (
            "Cl",
            "Brønsted acid · Inorganic compound",
            "Corrosive · Segregate from bases",
        ),
        "7647-14-5": ("[Na+].[Cl-]", "Inorganic salt", "Ambient temperature"),
        "64-19-7": (
            "CC(=O)O",
            "Brønsted acid · Organic compound",
            "Corrosive · Flammable",
        ),
        "67-68-5": (
            "CS(C)=O",
            "Polar aprotic solvent · Organic compound",
            "Ambient temperature",
        ),
        "77-86-1": (
            "NC(CO)(CO)CO",
            "Buffering base · Organic compound",
            "Ambient temperature",
        ),
        "7550-45-0": (
            "Cl[Ti](Cl)(Cl)Cl",
            "Lewis acid · Inorganic compound · Moisture reactive",
            "Corrosive · Water reactive · Segregate from bases",
        ),
        "109-72-8": (
            "[Li]CCCC",
            "Organometallic · Pyrophoric · Reducing agent",
            "Flammable · Water reactive · Locked storage",
        ),
        "76189-55-4": (
            "P(c1ccccc1)(c1ccccc1)c1ccc2ccccc2c1-c1c(P(c2ccccc2)c2ccccc2)ccc2ccccc12",
            "Chiral ligand · Phosphine ligand · Organophosphorus compound",
            "Ambient temperature · Keep away from oxidizers",
        ),
        "210169-54-3": (
            "C1OC2=C(O1)C(=C(C=C2)P(C3=CC=CC=C3)C4=CC=CC=C4)C5=C(C=CC6=C5OCO6)P(C7=CC=CC=C7)C8=CC=CC=C8",
            "Chiral ligand · Phosphine ligand · Organophosphorus compound",
            "Ambient temperature · Keep away from oxidizers",
        ),
    }
    frame["SMILES"] = frame["CAS number"].map(
        lambda cas: chemistry_metadata.get(cas, ("Not available", "", ""))[0]
    )
    frame["Chemical labels"] = frame["CAS number"].map(
        lambda cas: chemistry_metadata.get(cas, ("", "Unclassified", ""))[1]
    )
    frame["Storage constraints"] = frame["CAS number"].map(
        lambda cas: chemistry_metadata.get(cas, ("", "", "Manual review"))[2]
    )
    frame["Expiry state"] = frame["Expiry date"].apply(
        lambda value: (
            "Expired"
            if value < today
            else "Expiring soon"
            if value <= today + timedelta(days=30)
            else "Current"
        )
    )
    frame["Status"] = frame.apply(
        lambda row: (
            "Expired"
            if row["Expiry state"] == "Expired"
            else "Low stock"
            if row["Quantity"] < 10
            else "Available"
        ),
        axis=1,
    )
    return frame


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
    """Compile an allowlisted inventory intent into SQL plus bound parameters."""
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
        "ethanol": "Ethanol",
        "methanol": "Methanol",
        "acetonitrile": "Acetonitrile",
        "dcm": "Dichloromethane",
        "dichloromethane": "Dichloromethane",
        "binap": "(R)-BINAP",
        "segphos": "(S)-SEGPHOS",
    }
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
                "SELECT * FROM inventory\n"
                "WHERE LOWER(chemical_name) = LOWER(?)\n"
                "  AND quantity > ? AND status <> ?;"
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
                "SELECT * FROM inventory\n"
                "WHERE manufacturer = ? AND quantity < ?\n"
                "  AND quantity > ? AND status <> ?;"
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
                "SELECT * FROM inventory\n"
                "WHERE expiry_date <= CURRENT_DATE + INTERVAL '30 days';"
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
                "SELECT storage_location, COUNT(*) AS records\n"
                "FROM inventory WHERE quantity > ?\n"
                "GROUP BY storage_location;"
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
    query: str, frame: pd.DataFrame
) -> dict[str, Any]:
    """Route chemistry concepts before structured inventory filters."""
    normalized = query.lower().strip()
    chemical_signals = (
        "chiral",
        "asymmetric",
        "ligand",
        "protic",
        "nitrile",
        "cyano",
        "lewis acid",
        "organometallic",
        "organolithium",
        "substructure",
    )
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
    if any(signal in normalized for signal in chemical_signals):
        return {
            "route": "unsupported",
            "route_label": "Chemistry translation unavailable",
            "interpretation": (
                "This chemistry concept needs a reviewed SMARTS translation before search."
            ),
            "query_code": "",
            "parameters": [],
            "results": empty_inventory_result(frame),
            "warning": "No model-only availability answer was generated.",
        }
    return compile_structured_query(query, frame)


def interpret_sample_query(
    query: str, frame: pd.DataFrame
) -> tuple[str, str, pd.DataFrame]:
    """Compatibility wrapper for the structured inventory query helper."""
    plan = compile_structured_query(query, frame)
    return plan["interpretation"], plan["query_code"], plan["results"]


def render_topbar() -> None:
    st.markdown(
        """
        <div class="topbar">
            <div class="brand">
                <div class="brand-mark">LM</div>
                <div>
                    <div class="brand-name">LabMind</div>
                    <div class="brand-subtitle">Reagent intelligence</div>
                </div>
            </div>
            <div class="topbar-note">
                <span class="topbar-note-dot"></span>
                Safety-first workflow
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_hero() -> None:
    st.markdown(
        """
        <section class="hero">
            <div class="hero-kicker">Verified lab inventory</div>
            <h1 class="hero-title">
                Know what’s in the lab.<br>
                <span>And what it can do.</span>
            </h1>
            <p class="hero-copy">
                Receive reagents with a reviewable trail, classify their chemical
                function, and ask inventory questions with evidence behind every answer.
            </p>
            <div class="capability-rail" aria-label="LabMind capabilities">
                <div class="capability">
                    <span>01</span>
                    <strong>Label to order</strong>
                    <small>Four fields, verified</small>
                </div>
                <div class="capability">
                    <span>02</span>
                    <strong>Chemistry to storage</strong>
                    <small>AI labels, hard safety rules</small>
                </div>
                <div class="capability">
                    <span>03</span>
                    <strong>Question to evidence</strong>
                    <small>Structure and stock checked</small>
                </div>
            </div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def render_section_header(eyebrow: str, title: str, copy: str) -> None:
    st.markdown(
        f"""
        <div class="section-header">
            <div class="section-eyebrow">{escaped(eyebrow)}</div>
            <h2 class="section-title">{escaped(title)}</h2>
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
        items.append(
            f'<div class="step {state}"><strong>0{index}</strong>{escaped(label)}</div>'
        )
    st.markdown(f'<div class="stepper">{"".join(items)}</div>', unsafe_allow_html=True)


def initialize_extraction_state() -> None:
    result = get_sample_extraction_result()
    for field, value in result.items():
        st.session_state[f"add_field_{field}"] = value
    st.session_state["add_extraction_complete"] = True
    st.session_state["add_confirmation"] = None
    st.session_state["add_stage"] = "Details"
    st.session_state.setdefault("add_order_scenario", "Unique match")
    synchronize_classification_state()


def render_upload_step() -> bytes | None:
    render_section_header(
        "Step 1",
        "Add a reagent label",
        "Choose a clear photo of the bottle or package label.",
    )
    upload_key = f"label_upload_{st.session_state.get('add_upload_nonce', 0)}"
    uploaded_file = st.file_uploader(
        "Reagent label",
        type=["png", "jpg", "jpeg", "webp"],
        accept_multiple_files=False,
        key=upload_key,
        label_visibility="collapsed",
    )
    if uploaded_file is None:
        st.markdown(
            '<p class="upload-hint">PNG, JPG, or WebP · a straight-on photo works best.</p>',
            unsafe_allow_html=True,
        )
        return None

    contents = uploaded_file.getvalue()
    signature = uploaded_file_signature(contents)
    if st.session_state.get("add_file_signature") != signature:
        clear_state_keys(st.session_state)
        st.session_state["add_file_signature"] = signature
        st.session_state["add_upload_time"] = datetime.now().strftime("%H:%M")

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
        initialize_extraction_state()
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
        "Review extracted fields",
        "Confirm the label details and correct anything that needs attention.",
    )
    st.markdown(
        '<div class="status-line"><span class="status-dot"></span>Fields are ready for review</div>',
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
    selected_class = " selected" if selected else ""
    st.markdown(
        f"""
        <div class="order-card{selected_class}">
            <div class="order-id">{escaped(order["order_id"])} · {escaped(order["score"])} match</div>
            <div class="order-name">{escaped(order["chemical_name"])}</div>
            <div class="order-detail">
                CAS {escaped(order["cas_number"])} · {escaped(order["manufacturer"])} ·
                {escaped(order["quantity"])}<br>{escaped(order["explanation"])}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_order_match_step() -> None:
    if not st.session_state.get("add_extraction_complete"):
        return
    render_section_header(
        "Step 3",
        "Connect the incoming order",
        "Review the closest pending-order candidates before registration.",
    )
    with st.expander("Preview match outcomes"):
        st.selectbox(
            "Match result",
            ["Unique match", "Multiple matches", "No match"],
            key="add_order_scenario",
            on_change=clear_order_selection,
        )

    scenario = st.session_state.get("add_order_scenario", "Unique match")
    matches = get_sample_order_matches(scenario)
    if scenario == "Unique match":
        selected = matches[0]
        st.session_state["add_selected_order"] = selected["order_id"]
        st.session_state["add_register_without_order"] = False
        render_order_card(selected, selected=True)
    elif scenario == "Multiple matches":
        options = {order["order_id"]: order for order in matches}
        selected_id = st.selectbox(
            "Select the matching order",
            list(options),
            format_func=lambda value: (
                f'{value} · {options[value]["manufacturer"]} · {options[value]["quantity"]}'
            ),
            key="add_selected_order",
        )
        st.session_state["add_register_without_order"] = False
        render_order_card(options[selected_id], selected=True)
        with st.expander("Compare all candidates"):
            comparison = pd.DataFrame(
                [
                    {
                        "Order": order["order_id"],
                        "Manufacturer": order["manufacturer"],
                        "Quantity": order["quantity"],
                        "Match": order["score"],
                    }
                    for order in matches
                ]
            )
            st.dataframe(comparison, hide_index=True, width="stretch")
    else:
        st.session_state.pop("add_selected_order", None)
        st.warning("No pending order confidently matches these label details.")
        st.checkbox(
            "Register without a linked order",
            key="add_register_without_order",
        )


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
    return {
        "chemical_name": st.session_state.get("add_field_chemical_name", ""),
        "cas_number": st.session_state.get("add_field_cas_number", ""),
        "specification": st.session_state.get("add_field_specification", ""),
        "batch_number": st.session_state.get("add_field_batch_number", ""),
        "manufacturer": st.session_state.get("add_field_manufacturer", ""),
        "expiry_date": expiry.isoformat() if hasattr(expiry, "isoformat") else str(expiry),
        "quantity": st.session_state.get("add_field_quantity", 0),
        "unit": st.session_state.get("add_field_unit", ""),
        "confidence": st.session_state.get("add_field_confidence", 0) / 100,
        "pending_order": selected_order,
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
    summary_values = [
        ("Chemical", payload["chemical_name"]),
        ("CAS number", payload["cas_number"]),
        ("Batch", payload["batch_number"]),
        ("Manufacturer", payload["manufacturer"]),
        ("Quantity", f'{payload["quantity"]:g} {payload["unit"]}'),
        ("Pending order", payload["pending_order"] or "Selection required"),
        (
            "Chemical functions",
            " · ".join(payload["chemical_labels"]) or "Review required",
        ),
        (
            "Storage constraints",
            " · ".join(payload["storage_constraints"]) or "Review required",
        ),
        ("Storage", payload["storage_location"]),
        ("Storage rule", payload["storage_rule"]),
    ]
    summary = "".join(
        f"""
        <div class="summary-item">
            <div class="summary-label">{escaped(label)}</div>
            <div class="summary-value">{escaped(value)}</div>
        </div>
        """
        for label, value in summary_values
    )
    st.markdown(f'<div class="summary-grid">{summary}</div>', unsafe_allow_html=True)
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
        st.session_state["add_confirmation"] = confirm_sample_registration(
            payload,
            reviewed=reviewed,
        )

    confirmation = st.session_state.get("add_confirmation")
    if confirmation:
        st.markdown(
            f"""
            <div class="confirmation">
                <div class="confirmation-id">{escaped(confirmation["record_id"])}</div>
                <div class="confirmation-title">Registration draft complete</div>
                <p class="section-copy">
                    The reviewed record is ready to sync with the inventory service.
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
    render_section_header(
        "Reagent intake",
        "Register with confidence",
        "Move from a label photo to a reviewed storage decision without losing the evidence.",
    )
    render_stepper()
    upload_key = f"label_upload_{st.session_state.get('add_upload_nonce', 0)}"
    has_upload = st.session_state.get(upload_key) is not None

    if not has_upload:
        with st.container(key="intake_start"):
            with st.container(border=True, key="upload_panel"):
                render_upload_step()
        return

    with st.container(key="intake_workspace"):
        left, right = st.columns([0.72, 1.28], gap="medium")
        with left:
            with st.container(border=True, key="upload_panel"):
                uploaded_contents = render_upload_step()
        with right:
            if uploaded_contents is None:
                return
            if not st.session_state.get("add_extraction_complete"):
                with st.container(border=True, key="review_placeholder"):
                    render_section_header(
                        "Ready to review",
                        "Extract four label fields",
                        "The extracted values stay editable before any inventory decision is prepared.",
                    )
                    st.markdown(
                        """
                        <div class="preview-list">
                            <div><span>01</span><strong>CAS number</strong></div>
                            <div><span>02</span><strong>Specification</strong></div>
                            <div><span>03</span><strong>Batch or lot</strong></div>
                            <div><span>04</span><strong>Manufacturer</strong></div>
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


def render_inventory_results(frame: pd.DataFrame) -> None:
    render_inventory_metrics(frame)
    if frame.empty:
        st.markdown(
            '<div class="empty-state">No inventory records match these filters.</div>',
            unsafe_allow_html=True,
        )
        return

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
    st.text_area(
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
    ):
        st.session_state["query_natural_plan"] = route_natural_language_query(
            st.session_state.get("query_natural_text", ""),
            frame,
        )

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
    if not plan:
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
            ("02 · Compile", "Bound SQL filter"),
            ("03 · Execute", "Inventory database"),
            ("04 · Return", "Live record state"),
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
        code_language = "sql" if plan["route"] == "structured" else None
        st.code(plan["query_code"], language=code_language)
    if plan.get("parameters"):
        st.caption(
            "Bound parameters / required labels: "
            + " · ".join(str(value) for value in plan["parameters"])
        )
    if plan.get("warning"):
        st.warning(plan["warning"])
    if plan["route"] == "chemical" and not plan.get("warning"):
        st.success(
            f'{len(plan["results"])} verified on-hand match(es) · '
            f'{plan.get("skipped", 0)} structure record(s) skipped'
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
        render_inventory_results(results)
    st.markdown(
        '<p class="quiet-note">Every answer is derived from the loaded inventory snapshot; the language layer never invents stock state.</p>',
        unsafe_allow_html=True,
    )


def main() -> None:
    st.set_page_config(
        page_title="LabMind",
        page_icon="L",
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
