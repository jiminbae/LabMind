# LabMind

Streamlit UI prototype for the CS Team B role.

The repository also includes a static browser version in `site/` for GitHub
Pages. It preserves the image preview and mock recognition flow without running
Python on the server.

## Run

```powershell
pip install -r requirements.txt
streamlit run app.py
```

## Unit 1 interface

`app_v5.py` contains the next LabMind interface for reagent registration and
inventory discovery.

```powershell
streamlit run app_v5.py
```

This milestone is UI-only. Label extraction, order matching, storage guidance,
registration, and inventory records use deterministic sample data. No backend,
OCR provider, or database is connected. Future integration points are marked
with focused `TODO` comments in `app_v5.py`.

## GitHub Pages

Pushes that change `site/` on the `frontend` branch deploy through
`.github/workflows/deploy-pages.yml`. The repository owner must select
**GitHub Actions** under **Settings → Pages → Build and deployment** once.

## Current Scope

- Image file upload
- Upload success display
- Uploaded image preview
- Mock OCR JSON result display
- Basic recognized-field table for later integration with CS Team A
