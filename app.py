import html
import json
import os
import tempfile
from datetime import datetime
from pathlib import Path

import streamlit as st

from backend.pipeline import analyze_label


STREAMLIT_SECRET_NAMES = (
    "LABMIND_PROVIDER",
    "LABMIND_VISION_MODE",
    "OPENAI_API_KEY",
    "OPENAI_MODEL",
    "UNIVIBE_API_KEY",
    "UNIVIBE_BASE_URL",
    "UNIVIBE_MODEL",
)


def apply_theme() -> None:
    st.markdown(
        """
        <style>
        :root {
            --bg: #f6f7f9;
            --surface: #ffffff;
            --ink: #17202e;
            --muted: #697386;
            --line: #dde3ea;
            --teal: #0f766e;
            --blue: #2563eb;
            --coral: #d9543f;
            --amber: #b7791f;
        }

        .stApp {
            background:
                linear-gradient(180deg, #ffffff 0%, var(--bg) 46%, #eef3f5 100%);
            color: var(--ink);
        }

        div.block-container {
            max-width: 1180px;
            padding-top: 2.1rem;
            padding-bottom: 3rem;
        }

        header[data-testid="stHeader"] {
            background: rgba(255, 255, 255, 0);
        }

        #MainMenu,
        footer {
            visibility: hidden;
        }

        h1, h2, h3, p {
            letter-spacing: 0;
        }

        .labmind-topbar {
            align-items: center;
            border-bottom: 1px solid var(--line);
            display: flex;
            gap: 16px;
            justify-content: space-between;
            margin-bottom: 34px;
            padding-bottom: 18px;
        }

        .labmind-mark {
            align-items: center;
            display: flex;
            gap: 12px;
        }

        .labmind-logo {
            align-items: center;
            background: var(--ink);
            border-radius: 8px;
            color: #ffffff;
            display: inline-flex;
            font-size: 15px;
            font-weight: 760;
            height: 38px;
            justify-content: center;
            width: 38px;
        }

        .labmind-name {
            color: var(--ink);
            font-size: 19px;
            font-weight: 760;
            line-height: 1.1;
        }

        .labmind-sub {
            color: var(--muted);
            font-size: 13px;
            margin-top: 3px;
        }

        .labmind-status {
            align-items: center;
            color: var(--muted);
            display: flex;
            font-size: 13px;
            gap: 10px;
            white-space: nowrap;
        }

        .status-dot {
            background: var(--teal);
            border-radius: 999px;
            box-shadow: 0 0 0 5px rgba(15, 118, 110, 0.12);
            display: inline-block;
            height: 8px;
            width: 8px;
        }

        .hero-title {
            color: var(--ink);
            font-size: 46px;
            font-weight: 780;
            line-height: 1.04;
            margin: 0 0 12px 0;
            max-width: 780px;
        }

        .hero-copy {
            color: var(--muted);
            font-size: 17px;
            line-height: 1.65;
            margin: 0 0 26px 0;
            max-width: 720px;
        }

        .chip-row {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-bottom: 24px;
        }

        .chip {
            border: 1px solid var(--line);
            border-radius: 8px;
            color: var(--muted);
            font-size: 13px;
            padding: 7px 10px;
        }

        .section-label {
            color: var(--muted);
            font-size: 12px;
            font-weight: 760;
            letter-spacing: .08em;
            margin-bottom: 8px;
            text-transform: uppercase;
        }

        .panel-title {
            color: var(--ink);
            font-size: 22px;
            font-weight: 760;
            margin: 0 0 5px 0;
        }

        .panel-copy {
            color: var(--muted);
            font-size: 14px;
            line-height: 1.55;
            margin: 0 0 18px 0;
        }

        div[data-testid="stFileUploader"] section {
            background: #ffffff;
            border: 1px dashed #aeb8c4;
            border-radius: 8px;
            padding: 18px;
        }

        div[data-testid="stFileUploader"] section:hover {
            border-color: var(--teal);
        }

        div[data-testid="stFileUploader"] button {
            background: var(--ink);
            border: 1px solid var(--ink);
            border-radius: 8px;
            color: #ffffff;
            font-weight: 700;
        }

        div[data-testid="stFileUploader"] button p,
        div[data-testid="stFileUploader"] button span {
            color: #ffffff;
        }

        div[data-testid="stFileUploader"] button:hover,
        div[data-testid="stFileUploader"] button:focus {
            background: var(--teal);
            border-color: var(--teal);
            color: #ffffff;
        }

        div[data-testid="stFileUploader"] button:hover p,
        div[data-testid="stFileUploader"] button:hover span,
        div[data-testid="stFileUploader"] button:focus p,
        div[data-testid="stFileUploader"] button:focus span {
            color: #ffffff;
        }

        .stAlert {
            border-radius: 8px;
        }

        div[data-testid="stMetric"] {
            background: #ffffff;
            border: 1px solid var(--line);
            border-radius: 8px;
            padding: 14px 14px 10px 14px;
        }

        div[data-testid="stMetric"] div,
        div[data-testid="stMetric"] label,
        div[data-testid="stMetric"] p,
        div[data-testid="stMetric"] span {
            color: var(--ink);
        }

        div[data-testid="stMetricLabel"] p {
            color: var(--muted);
            font-size: 12px;
            font-weight: 650;
        }

        div[data-testid="stMetricValue"] {
            color: var(--ink);
            font-size: 25px;
            font-weight: 760;
        }

        div[data-testid="stMetricValue"] div,
        div[data-testid="stMetricValue"] p {
            color: var(--ink);
        }

        .empty-preview {
            align-items: center;
            background:
                linear-gradient(135deg, rgba(15,118,110,.08), rgba(37,99,235,.05)),
                #ffffff;
            border: 1px solid var(--line);
            border-radius: 8px;
            color: var(--muted);
            display: flex;
            min-height: 280px;
            justify-content: center;
            padding: 24px;
            text-align: center;
        }

        .result-card {
            background: #ffffff;
            border: 1px solid var(--line);
            border-radius: 8px;
            padding: 18px;
        }

        .result-pills {
            align-items: center;
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-bottom: 18px;
        }

        .result-pill {
            align-items: center;
            border-radius: 999px;
            display: inline-flex;
            font-size: 12px;
            font-weight: 760;
            gap: 7px;
            padding: 7px 10px;
        }

        .result-pill.positive {
            background: rgba(15, 118, 110, 0.11);
            color: #0d665f;
        }

        .result-pill.neutral {
            background: rgba(37, 99, 235, 0.10);
            color: #1d4ed8;
        }

        .result-pill.warning {
            background: rgba(183, 121, 31, 0.13);
            color: #8a5a13;
        }

        .product-name {
            color: var(--ink);
            font-size: 32px;
            font-weight: 800;
            line-height: 1.05;
            margin: 0;
        }

        .product-subtitle {
            color: var(--muted);
            font-size: 14px;
            margin: 8px 0 18px 0;
        }

        .detail-grid {
            display: grid;
            gap: 10px;
            grid-template-columns: repeat(3, minmax(0, 1fr));
        }

        .detail-card {
            background: #f8fafb;
            border: 1px solid var(--line);
            border-radius: 8px;
            min-height: 82px;
            padding: 12px;
        }

        .field-label {
            color: var(--muted);
            font-size: 12px;
            font-weight: 720;
            margin-bottom: 4px;
            text-transform: uppercase;
        }

        .field-value {
            color: var(--ink);
            font-size: 16px;
            font-weight: 680;
        }

        .stExpander {
            border-color: var(--line);
        }

        .footer-note {
            border-top: 1px solid var(--line);
            color: var(--muted);
            font-size: 13px;
            margin-top: 28px;
            padding-top: 18px;
        }

        @media (max-width: 760px) {
            .labmind-topbar {
                align-items: flex-start;
                flex-direction: column;
            }

            .hero-title {
                font-size: 34px;
            }

            .detail-grid {
                grid-template-columns: 1fr;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def format_file_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes / (1024 * 1024):.1f} MB"


def configure_runtime_from_streamlit_secrets() -> None:
    """Expose supported Streamlit secrets to the backend as environment variables."""

    try:
        secrets = dict(st.secrets)
    except Exception:
        return

    for name in STREAMLIT_SECRET_NAMES:
        if os.environ.get(name):
            continue
        value = secrets.get(name)
        if value is not None and str(value).strip():
            os.environ[name] = str(value)


def analyze_uploaded_file(uploaded_file) -> dict:
    """Persist one upload temporarily, run the backend, and remove the file."""

    suffix = Path(uploaded_file.name).suffix.lower() or ".png"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as handle:
        handle.write(uploaded_file.getbuffer())
        image_path = Path(handle.name)

    try:
        return analyze_label(image_path).to_dict()
    finally:
        image_path.unlink(missing_ok=True)


def display_value(value, fallback: str = "Not available") -> str:
    text = str(value).strip() if value is not None else ""
    return html.escape(text or fallback)

def render_topbar() -> None:
    st.markdown(
        """
        <div class="labmind-topbar">
            <div class="labmind-mark">
                <div class="labmind-logo">LM</div>
                <div>
                    <div class="labmind-name">LabMind</div>
                    <div class="labmind-sub">Inventory-aware label intelligence</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_hero() -> None:
    st.markdown(
        """
        <h1 class="hero-title">Turn lab labels into structured inventory data.</h1>
        <p class="hero-copy">
            LabMind gives the team a clean review surface for reagent label OCR,
            extracted fields, confidence checks, and the next integration step.
        </p>
        """,
        unsafe_allow_html=True,
    )


def render_result_card(result: dict) -> None:
    ocr = result.get("ocr") or {}
    inventory = result.get("inventory") or {}
    expiry_warning = result.get("expiry_warning") or {}

    status_value = result.get("status") or "failed"
    status = getattr(status_value, "value", status_value)
    expiry_state_value = expiry_warning.get("state") or "not checked"
    expiry_state = getattr(expiry_state_value, "value", expiry_state_value)
    confidence = float(ocr.get("confidence") or 0.0)

    status_class = "positive" if status == "success" else "warning"
    confidence_label = f"{confidence * 100:.0f}% confidence"
    status_label = display_value(str(status).title())
    product_name = display_value(ocr.get("product_name"), "Unrecognized product")
    brand = display_value(ocr.get("brand"), "Unknown brand")
    catalog_number = display_value(ocr.get("catalog_number"), "Not visible")
    lot_number = display_value(ocr.get("lot_number"))
    expiry_date = display_value(ocr.get("expiry_date"))

    if inventory:
        inventory_status = "Found" if inventory.get("found") else "Not found"
    else:
        inventory_status = "Not checked"

    st.markdown(
        f"""
        <div class="result-card">
            <div class="result-pills">
                <span class="result-pill {status_class}">{confidence_label}</span>
                <span class="result-pill neutral">{status_label}</span>
            </div>
            <h3 class="product-name">{product_name}</h3>
            <div class="product-subtitle">
                {brand} &middot; Catalog {catalog_number}
            </div>
            <div class="detail-grid">
                <div class="detail-card">
                    <div class="field-label">Lot number</div>
                    <div class="field-value">{lot_number}</div>
                </div>
                <div class="detail-card">
                    <div class="field-label">Expiration</div>
                    <div class="field-value">{expiry_date}</div>
                </div>
                <div class="detail-card">
                    <div class="field-label">Inventory</div>
                    <div class="field-value">{display_value(inventory_status)}</div>
                </div>
                <div class="detail-card">
                    <div class="field-label">Quantity</div>
                    <div class="field-value">{display_value(inventory.get("quantity"))}</div>
                </div>
                <div class="detail-card">
                    <div class="field-label">Location</div>
                    <div class="field-value">{display_value(inventory.get("location"))}</div>
                </div>
                <div class="detail-card">
                    <div class="field-label">Expiry state</div>
                    <div class="field-value">{display_value(str(expiry_state).title())}</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    st.set_page_config(
        page_title="LabMind",
        page_icon="L",
        layout="wide",
    )

    configure_runtime_from_streamlit_secrets()
    apply_theme()
    render_topbar()
    render_hero()

    preview_col, result_col = st.columns([1.05, 1], gap="large")

    with preview_col:
        st.markdown('<div class="section-label">Input</div>', unsafe_allow_html=True)
        st.markdown('<h2 class="panel-title">Label preview</h2>', unsafe_allow_html=True)
        st.markdown(
            '<p class="panel-copy">Upload a reagent bottle label for backend analysis.</p>',
            unsafe_allow_html=True,
        )
        uploaded_file = st.file_uploader(
            "Label image",
            type=["png", "jpg", "jpeg", "webp"],
            accept_multiple_files=False,
            label_visibility="collapsed",
        )

        if uploaded_file is None:
            st.markdown(
                '<div class="empty-preview">No image selected</div>',
                unsafe_allow_html=True,
            )
        else:
            file_suffix = Path(uploaded_file.name).suffix.lower()
            st.image(uploaded_file, caption=uploaded_file.name, use_container_width=True)
            meta_cols = st.columns(3)
            meta_cols[0].metric("Type", uploaded_file.type or file_suffix)
            meta_cols[1].metric("Size", format_file_size(uploaded_file.size))
            meta_cols[2].metric("Uploaded", datetime.now().strftime("%H:%M"))

    with result_col:
        st.markdown('<div class="section-label">Output</div>', unsafe_allow_html=True)
        st.markdown('<h2 class="panel-title">Recognition result</h2>', unsafe_allow_html=True)
        st.markdown(
            '<p class="panel-copy">Run OCR, inventory, expiry, and recommendation analysis.</p>',
            unsafe_allow_html=True,
        )

        if uploaded_file is None:
            st.info("Result will appear after an image is selected.")
        else:
            file_signature = f"{uploaded_file.name}:{uploaded_file.size}"
            if st.button("Analyze label", type="primary", use_container_width=True):
                try:
                    with st.spinner("Analyzing the reagent label..."):
                        payload = analyze_uploaded_file(uploaded_file)
                    st.session_state["labmind_result"] = payload
                    st.session_state["labmind_file_signature"] = file_signature
                except Exception as error:
                    st.session_state.pop("labmind_result", None)
                    st.session_state.pop("labmind_file_signature", None)
                    st.error(f"Analysis could not start ({type(error).__name__}).")

            payload = None
            if st.session_state.get("labmind_file_signature") == file_signature:
                payload = st.session_state.get("labmind_result")

            if payload is None:
                st.info("Select Analyze label to run the backend.")
            else:
                ocr = payload.get("ocr") or {}
                status_value = payload.get("status") or "failed"
                status = getattr(status_value, "value", status_value)

                if status == "success":
                    st.success("Backend analysis completed.")
                else:
                    st.warning(
                        payload.get("error_message")
                        or "Recognition was incomplete. Review the partial fields below."
                    )

                metric_cols = st.columns(2)
                metric_cols[0].metric(
                    "Confidence",
                    f"{float(ocr.get('confidence') or 0.0) * 100:.0f}%",
                )
                metric_cols[1].metric("Status", str(status).title())

                render_result_card(payload)

                alternatives = payload.get("alternatives") or []
                if alternatives:
                    st.markdown("### Recommended alternatives")
                    alternative_rows = []
                    for alternative in alternatives:
                        product = alternative.get("product") or {}
                        alternative_rows.append(
                            {
                                "Catalog": alternative.get("catalog_number"),
                                "Compatibility": alternative.get("compatibility_note"),
                                "Brand": product.get("brand"),
                                "Price (USD)": product.get("price_usd"),
                            }
                        )
                    st.dataframe(
                        alternative_rows,
                        use_container_width=True,
                        hide_index=True,
                    )

                with st.expander("Raw JSON"):
                    st.code(
                        json.dumps(payload, ensure_ascii=False, indent=2),
                        language="json",
                    )

if __name__ == "__main__":
    main()
