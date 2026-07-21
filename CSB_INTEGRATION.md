# CS B Integration Handoff

## What is connected

The Streamlit upload flow now calls the real backend through:

```python
from backend.pipeline import analyze_label

result = analyze_label(image_path)
payload = result.to_dict()
```

The UI temporarily saves the uploaded image, runs OCR and downstream analysis, and deletes the temporary file afterward. It displays partial OCR fields even when the catalog number is missing.

## Field mapping

| UI field | Backend field |
| --- | --- |
| Product name | `payload["ocr"]["product_name"]` |
| Brand | `payload["ocr"]["brand"]` |
| Catalog number | `payload["ocr"]["catalog_number"]` |
| Lot number | `payload["ocr"]["lot_number"]` |
| Expiry date | `payload["ocr"]["expiry_date"]` |
| Confidence | `payload["ocr"]["confidence"]` |
| Inventory quantity | `payload["inventory"]["quantity"]` |
| Inventory location | `payload["inventory"]["location"]` |
| Expiry state | `payload["expiry_warning"]["state"]` |
| Alternatives | `payload["alternatives"]` |

Always handle `inventory`, `expiry_warning`, and `product` as nullable values because the pipeline stops safely when no catalog number is visible.

## Local run

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
streamlit run app.py
```

Mock mode works without credentials. For live mode, copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml`, set `LABMIND_VISION_MODE = "live"`, choose one provider, and add only that provider's key.

## Deployment

Deploy `app.py` on a Python-capable Streamlit host. In the deployment settings, select this repository and integration branch, set `app.py` as the entry point, and paste the live configuration into the platform's Secrets field.

Do not put a provider key in `site/app.js`. The `site/` directory is a static GitHub Pages demo and cannot run the Python backend securely.

## Verification

```powershell
python -m unittest discover -s tests
python -m py_compile app.py
```

Expected behavior:

- A label with a catalog number continues into inventory, expiry, and recommendation analysis.
- A label without a catalog number shows a failed status while retaining any recognized product, lot, expiry, brand, and confidence fields.
- Selecting a new file does not reuse the previous file's result.
