import json
from datetime import datetime
from pathlib import Path

import streamlit as st


MOCK_RESULT = {
    "status": "success",
    "recognized_text": {
        "product_name": "Ethanol",
        "brand": "Sigma-Aldrich",
        "catalog_no": "459836",
        "expiration_date": "2027-04-30",
        "quantity": "500 mL",
        "storage": "Room temperature",
    },
    "confidence": 0.92,
    "review_state": "Ready for inventory match",
}


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
            <div class="labmind-status">
                <span class="status-dot"></span>
                UI prototype
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
        <div class="chip-row">
            <span class="chip">Streamlit UI</span>
            <span class="chip">Image upload</span>
            <span class="chip">Mock JSON</span>
            <span class="chip">CS Team B</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_result_card(result: dict) -> None:
    recognized_text = result["recognized_text"]
    confidence = f"{result['confidence'] * 100:.0f}% confidence"
    status = result["status"].title()

    st.markdown(
        f"""
        <div class="result-card">
            <div class="result-pills">
                <span class="result-pill positive">{confidence}</span>
                <span class="result-pill neutral">{status}</span>
            </div>
            <h3 class="product-name">{recognized_text["product_name"]}</h3>
            <div class="product-subtitle">
                {recognized_text["brand"]} · Catalog {recognized_text["catalog_no"]}
            </div>
            <div class="detail-grid">
                <div class="detail-card">
                    <div class="field-label">Expiration</div>
                    <div class="field-value">{recognized_text["expiration_date"]}</div>
                </div>
                <div class="detail-card">
                    <div class="field-label">Quantity</div>
                    <div class="field-value">{recognized_text["quantity"]}</div>
                </div>
                <div class="detail-card">
                    <div class="field-label">Storage</div>
                    <div class="field-value">{recognized_text["storage"]}</div>
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

    apply_theme()
    render_topbar()
    render_hero()

    preview_col, result_col = st.columns([1.05, 1], gap="large")

    with preview_col:
        st.markdown('<div class="section-label">Input</div>', unsafe_allow_html=True)
        st.markdown('<h2 class="panel-title">Label preview</h2>', unsafe_allow_html=True)
        st.markdown(
            '<p class="panel-copy">Upload a reagent bottle label for the review screen.</p>',
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
            '<p class="panel-copy">Mock result view prepared for the OCR script handoff.</p>',
            unsafe_allow_html=True,
        )

        if uploaded_file is None:
            st.info("Result will appear after an image is selected.")
        else:
            st.success(MOCK_RESULT["review_state"])
            metric_cols = st.columns(2)
            metric_cols[0].metric("Confidence", f"{MOCK_RESULT['confidence'] * 100:.0f}%")
            metric_cols[1].metric("Status", MOCK_RESULT["status"].title())

            render_result_card(MOCK_RESULT)

            with st.expander("Raw JSON"):
                st.code(
                    json.dumps(MOCK_RESULT, indent=2),
                    language="json",
                )

    st.markdown(
        '<div class="footer-note">LabMind prototype by CS Team B. Prepared for Streamlit, OCR script, and inventory CSV integration.</div>',
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
