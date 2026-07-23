from __future__ import annotations

import hashlib
import html
import json
from datetime import date, datetime, timedelta
from typing import Any, MutableMapping

import pandas as pd
import streamlit as st


ADD_STATE_KEYS = {
    "add_file_signature",
    "add_upload_time",
    "add_extraction_complete",
    "add_confirmation",
    "add_order_scenario",
    "add_selected_order",
    "add_register_without_order",
    "add_storage_location",
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


def apply_theme() -> None:
    st.markdown(
        """
        <style>
        :root {
            --canvas: #f5f5f7;
            --surface: rgba(255, 255, 255, 0.92);
            --surface-strong: #ffffff;
            --ink: #1d1d1f;
            --secondary: #6e6e73;
            --tertiary: #86868b;
            --line: rgba(0, 0, 0, 0.09);
            --line-strong: rgba(0, 0, 0, 0.14);
            --accent: #0071e3;
            --accent-hover: #0077ed;
            --teal: #087f75;
            --green: #248a3d;
            --amber: #a95d00;
            --red: #d70015;
            --shadow: 0 10px 34px rgba(0, 0, 0, 0.055);
        }

        html, body, [class*="css"] {
            font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display",
                "SF Pro Text", "Helvetica Neue", Arial, sans-serif;
        }

        .stApp {
            background:
                radial-gradient(circle at 88% 2%, rgba(0, 113, 227, 0.055), transparent 28rem),
                var(--canvas);
            color: var(--ink);
        }

        div.block-container {
            max-width: 1240px;
            padding: 1.4rem 2rem 4rem;
        }

        header[data-testid="stHeader"] {
            background: transparent;
        }

        #MainMenu, footer {
            visibility: hidden;
        }

        h1, h2, h3, p {
            color: var(--ink);
            letter-spacing: -0.015em;
        }

        .topbar {
            align-items: center;
            border-bottom: 1px solid var(--line);
            display: flex;
            justify-content: space-between;
            min-height: 58px;
            padding: 0 2px 14px;
        }

        .brand {
            align-items: center;
            display: flex;
            gap: 11px;
        }

        .brand-mark {
            align-items: center;
            background: var(--ink);
            border-radius: 11px;
            color: #fff;
            display: inline-flex;
            font-size: 13px;
            font-weight: 760;
            height: 36px;
            justify-content: center;
            letter-spacing: -0.02em;
            width: 36px;
        }

        .brand-name {
            color: var(--ink);
            font-size: 18px;
            font-weight: 720;
            line-height: 1.1;
        }

        .brand-subtitle {
            color: var(--secondary);
            font-size: 12px;
            margin-top: 3px;
        }

        .hero {
            padding: 58px 0 38px;
        }

        .hero-kicker {
            color: var(--accent);
            font-size: 13px;
            font-weight: 650;
            letter-spacing: 0.01em;
            margin-bottom: 12px;
        }

        .hero-title {
            color: var(--ink);
            font-size: clamp(42px, 6vw, 68px);
            font-weight: 710;
            letter-spacing: -0.055em;
            line-height: 0.98;
            margin: 0;
            max-width: 860px;
        }

        .hero-copy {
            color: var(--secondary);
            font-size: 18px;
            letter-spacing: -0.01em;
            line-height: 1.55;
            margin: 20px 0 0;
            max-width: 720px;
        }

        .section-header {
            margin: 8px 0 18px;
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
            font-size: 27px;
            font-weight: 680;
            letter-spacing: -0.035em;
            line-height: 1.1;
            margin: 0;
        }

        .section-copy {
            color: var(--secondary);
            font-size: 14px;
            line-height: 1.5;
            margin: 7px 0 0;
            max-width: 720px;
        }

        .stepper {
            background: rgba(255, 255, 255, 0.68);
            border: 1px solid var(--line);
            border-radius: 18px;
            display: grid;
            gap: 0;
            grid-template-columns: repeat(5, 1fr);
            margin: 4px 0 26px;
            overflow: hidden;
        }

        .step {
            border-right: 1px solid var(--line);
            color: var(--tertiary);
            font-size: 12px;
            padding: 14px 13px;
        }

        .step:last-child {
            border-right: 0;
        }

        .step strong {
            color: inherit;
            display: block;
            font-size: 11px;
            margin-bottom: 3px;
        }

        .step.active {
            background: var(--surface-strong);
            color: var(--accent);
        }

        .step.complete {
            color: var(--green);
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

        div[data-testid="stTabs"] [data-baseweb="tab-highlight"] {
            display: none;
        }

        div[data-testid="stTabs"] [data-baseweb="tab-border"] {
            display: none;
        }

        div[data-testid="stVerticalBlockBorderWrapper"] {
            background: var(--surface);
            border: 1px solid var(--line);
            border-radius: 20px;
            box-shadow: var(--shadow);
        }

        div[data-testid="stFileUploader"] section {
            background: rgba(245, 245, 247, 0.72);
            border: 1px dashed var(--line-strong);
            border-radius: 16px;
            min-height: 126px;
            padding: 22px;
            transition: border-color .18s ease, background .18s ease;
        }

        div[data-testid="stFileUploader"] section:hover {
            background: #fff;
            border-color: var(--accent);
        }

        div[data-testid="stFileUploader"] button,
        div.stButton > button,
        div[data-testid="stDownloadButton"] > button {
            border-radius: 999px;
            font-weight: 600;
            min-height: 40px;
            transition: all .18s ease;
        }

        div.stButton > button[kind="primary"] {
            background: var(--accent);
            border-color: var(--accent);
            color: white;
        }

        div.stButton > button[kind="primary"]:hover {
            background: var(--accent-hover);
            border-color: var(--accent-hover);
            box-shadow: 0 5px 16px rgba(0, 113, 227, 0.22);
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
            border-radius: 12px !important;
        }

        .empty-state {
            align-items: center;
            background: rgba(245, 245, 247, 0.72);
            border: 1px solid var(--line);
            border-radius: 16px;
            color: var(--secondary);
            display: flex;
            justify-content: center;
            min-height: 245px;
            padding: 26px;
            text-align: center;
        }

        .meta-grid, .summary-grid {
            display: grid;
            gap: 10px;
            grid-template-columns: repeat(3, minmax(0, 1fr));
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

        @media (max-width: 820px) {
            div.block-container {
                padding: 1rem 1rem 3rem;
            }

            .hero {
                padding: 42px 0 30px;
            }

            .hero-title {
                font-size: 43px;
            }

            .stepper {
                grid-template-columns: 1fr;
            }

            .step {
                border-bottom: 1px solid var(--line);
                border-right: 0;
                padding: 10px 13px;
            }

            .step:last-child {
                border-bottom: 0;
            }

            .meta-grid, .summary-grid, .metric-row {
                grid-template-columns: 1fr;
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


def get_sample_storage_recommendation() -> dict[str, Any]:
    """Temporary UI data. TODO: replace with rule_engine output."""
    return {
        "tags": ["Flammable", "Organic solvent"],
        "recommended_location": "Flammable Cabinet B",
        "reason": "Flammable organic solvent requiring dedicated cabinet storage.",
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


def cas_display_state(cas_number: str | None) -> tuple[str, str]:
    """Display-only format state. TODO: replace with cas_validator."""
    value = (cas_number or "").strip()
    if not value:
        return "CAS not provided", "warning"
    parts = value.split("-")
    if len(parts) == 3 and all(part.isdigit() for part in parts):
        return "CAS format check: Valid", "positive"
    return "CAS format check: Needs review", "warning"


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


def interpret_sample_query(
    query: str, frame: pd.DataFrame
) -> tuple[str, str, pd.DataFrame]:
    """Return a safe UI preview without generating or executing SQL."""
    normalized = query.lower().strip()
    if "sigma" in normalized and ("low" in normalized or "below" in normalized):
        result = frame[
            (frame["Manufacturer"] == "Sigma-Aldrich") & (frame["Quantity"] < 10)
        ]
        return (
            "Sigma-Aldrich records with fewer than 10 units in stock.",
            'FILTER manufacturer = "Sigma-Aldrich" AND quantity < 10',
            result.reset_index(drop=True),
        )
    if "expir" in normalized and ("30" in normalized or "soon" in normalized):
        result = frame[frame["Expiry state"].isin(["Expiring soon", "Expired"])]
        return (
            "Records that are expired or reach their expiry date within 30 days.",
            'FILTER expiry_state IN ["Expiring soon", "Expired"]',
            result.reset_index(drop=True),
        )
    if "flammable" in normalized:
        result = frame[frame["Storage location"].str.contains("Flammable", case=False)]
        return (
            "Records assigned to a flammable-material storage location.",
            'FILTER storage_location CONTAINS "Flammable"',
            result.reset_index(drop=True),
        )
    if "storage" in normalized and ("count" in normalized or "group" in normalized):
        return (
            "All records, grouped visually by storage location below.",
            "GROUP records BY storage_location",
            frame.reset_index(drop=True),
        )
    return (
        "A representative inventory result for interface review.",
        "PREVIEW first 5 inventory records",
        frame.head(5).reset_index(drop=True),
    )


def render_topbar() -> None:
    st.markdown(
        """
        <div class="topbar">
            <div class="brand">
                <div class="brand-mark">LM</div>
                <div>
                    <div class="brand-name">LabMind</div>
                    <div class="brand-subtitle">Reagent inventory workspace</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_hero() -> None:
    st.markdown(
        """
        <section class="hero">
            <div class="hero-kicker">A clearer way to manage the lab</div>
            <h1 class="hero-title">Every reagent.<br>Ready when you need it.</h1>
            <p class="hero-copy">
                Review label details, connect incoming orders, assign storage,
                and explore inventory from one focused workspace.
            </p>
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
        active_step = 2
    else:
        active_step = 1
    labels = [
        "Upload label",
        "Review fields",
        "Connect order",
        "Assign storage",
        "Confirm",
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
    st.session_state.setdefault("add_order_scenario", "Unique match")
    st.session_state.setdefault("add_storage_location", "Flammable Cabinet B")


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
            '<div class="empty-state">Drop a PNG, JPG, or WebP image here to begin.</div>',
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
        <div class="meta-grid">
            <div class="meta-item">
                <div class="meta-label">File</div>
                <div class="meta-value">{escaped(uploaded_file.name)}</div>
            </div>
            <div class="meta-item">
                <div class="meta-label">Type · Size</div>
                <div class="meta-value">{escaped(uploaded_file.type or "Image")} · {format_file_size(len(contents))}</div>
            </div>
            <div class="meta-item">
                <div class="meta-label">Uploaded</div>
                <div class="meta-value">{uploaded_at}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button(
        "Extract label",
        type="primary",
        width="stretch",
        key="extract_label",
    ):
        initialize_extraction_state()
    st.markdown(
        '<p class="quiet-note">This build uses representative values until label services are connected.</p>',
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
    left, right = st.columns(2, gap="large")
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
        selected_id = st.radio(
            "Select the matching order",
            list(options),
            format_func=lambda value: (
                f'{value} · {options[value]["manufacturer"]} · {options[value]["quantity"]}'
            ),
            key="add_selected_order",
        )
        st.session_state["add_register_without_order"] = False
        for order in matches:
            render_order_card(order, selected=order["order_id"] == selected_id)
    else:
        st.session_state.pop("add_selected_order", None)
        st.warning("No pending order confidently matches these label details.")
        st.checkbox(
            "Register without a linked order",
            key="add_register_without_order",
        )


def render_storage_step() -> None:
    if not st.session_state.get("add_extraction_complete"):
        return
    recommendation = get_sample_storage_recommendation()
    render_section_header(
        "Step 4",
        "Assign storage",
        "Review the suggested location and choose the final destination.",
    )
    tags = "".join(
        f'<span class="tag">{escaped(tag)}</span>' for tag in recommendation["tags"]
    )
    st.markdown(f'<div class="tag-row">{tags}</div>', unsafe_allow_html=True)
    st.markdown(
        f"""
        <div class="order-card selected">
            <div class="order-id">Recommended location</div>
            <div class="order-name">{escaped(recommendation["recommended_location"])}</div>
            <div class="order-detail">{escaped(recommendation["reason"])}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.selectbox(
        "Storage location",
        STORAGE_OPTIONS,
        key="add_storage_location",
    )
    st.markdown(
        '<p class="quiet-note">Confirm the final location against your laboratory safety policy.</p>',
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
        "storage_location": st.session_state.get("add_storage_location", ""),
    }


def clear_order_selection() -> None:
    st.session_state.pop("add_selected_order", None)
    st.session_state.pop("add_register_without_order", None)
    st.session_state.pop("add_confirmation", None)


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
        ("Storage", payload["storage_location"]),
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
                <div class="confirmation-title">Registration preview prepared</div>
                <p class="section-copy">
                    The reviewed payload is ready for a future backend handoff.
                    No database changes were made.
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


def render_add_tab() -> None:
    render_stepper()
    left, right = st.columns([0.9, 1.1], gap="large")
    with left:
        with st.container(border=True):
            uploaded_contents = render_upload_step()
    with right:
        if uploaded_contents is None:
            with st.container(border=True):
                render_section_header(
                    "Next",
                    "Review workspace",
                    "Extracted details and inventory decisions will appear here.",
                )
                st.markdown(
                    '<div class="empty-state">Add a label image to open the review workflow.</div>',
                    unsafe_allow_html=True,
                )
            return
        if not st.session_state.get("add_extraction_complete"):
            with st.container(border=True):
                render_section_header(
                    "Next",
                    "Review workspace",
                    "Select Extract label when the image is ready.",
                )
                st.markdown(
                    '<div class="empty-state">Label details will remain editable before confirmation.</div>',
                    unsafe_allow_html=True,
                )
            return
        with st.container(border=True):
            render_extraction_step()
        with st.container(border=True):
            render_order_match_step()
        with st.container(border=True):
            render_storage_step()
        with st.container(border=True):
            render_confirmation_step()


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
    st.dataframe(
        display_frame,
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


def render_natural_language_query(frame: pd.DataFrame) -> pd.DataFrame:
    st.text_area(
        "Ask about inventory",
        placeholder=(
            "Try “Show reagents expiring within 30 days” or "
            "“Find Sigma-Aldrich products with low stock.”"
        ),
        height=110,
        key="query_natural_text",
    )
    if st.button(
        "Preview results",
        type="primary",
        width="stretch",
        key="run_natural_query",
    ):
        interpretation, query_preview, result = interpret_sample_query(
            st.session_state.get("query_natural_text", ""),
            frame,
        )
        st.session_state["query_interpretation"] = interpretation
        st.session_state["query_plan"] = query_preview
        st.session_state["query_natural_results"] = result

    result = st.session_state.get("query_natural_results", frame.head(5))
    interpretation = st.session_state.get(
        "query_interpretation",
        "Enter a question to preview how inventory results could be organized.",
    )
    query_plan = st.session_state.get("query_plan", "AWAITING QUERY")
    st.markdown(
        f"""
        <div class="order-card selected">
            <div class="order-id">Interpretation preview</div>
            <div class="order-name">{escaped(interpretation)}</div>
            <div class="order-detail">No database query is executed in this interface.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.code(query_plan, language=None)
    return result


def render_query_tab() -> None:
    frame = load_sample_inventory()
    render_section_header(
        "Inventory",
        "Find what the lab has on hand",
        "Search by precise filters or describe what you are looking for.",
    )
    mode = st.radio(
        "Query mode",
        ["Basic filters", "Natural-language query"],
        horizontal=True,
        key="query_mode",
        label_visibility="collapsed",
    )
    with st.container(border=True):
        if mode == "Basic filters":
            results = render_basic_query(frame)
        else:
            results = render_natural_language_query(frame)
    render_inventory_results(results)
    st.markdown(
        '<p class="quiet-note">Inventory shown here is sample data for interface review.</p>',
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
    add_tab, query_tab = st.tabs(["Add Reagent", "Query Inventory"])
    with add_tab:
        render_add_tab()
    with query_tab:
        render_query_tab()


if __name__ == "__main__":
    main()
