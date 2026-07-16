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
