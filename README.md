# LabMind

LabMind is a focused reagent intake and inventory-discovery workspace.

The stable entrypoint is `app.py`, which loads the current interface from
`app_v5.py`. A static browser build remains in `site/` for GitHub Pages.

## Run

```powershell
pip install -r requirements.txt
streamlit run app.py
```

## Implemented workflows

- Label intake with a locally verified CAS check digit
- Real SQLite reagent-lot registration with a deterministic `LAB-0001` style
  record code and idempotent receipt keys
- CSV import, deterministic matching, and receipt completion for pending orders
- CAS-level, multi-label classification cache with an optional Gemini provider
- Deterministic, fail-closed storage assignment rules; AI never selects a cabinet
- Inventory search against the stored reagent rows, not a hard-coded snapshot
- Chemistry-meaning questions translated to reviewed SMARTS, matched with RDKit,
  then intersected with available, non-expired inventory

The language layer never determines whether an item is in stock. Availability,
quantity, expiry state, record IDs, order completion, and storage locations
remain deterministic database or rule-engine decisions.

## AI setup

The default is manual entry. The app never fills a label with sample values when
an API key is unavailable or a request fails.

1. Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml`.
2. Set `LABMIND_VISION_MODE = "live"`, `LABMIND_PROVIDER = "gemini"`, and a
   `GEMINI_API_KEY`.
3. Restart Streamlit.

Use `GEMINI_API_KEY` as the single key setting. If a legacy `GOOGLE_API_KEY`
secret is also present with a different value, remove it; the app rejects that
ambiguous configuration without displaying either secret.

Gemini can extract the printed chemical name, CAS number, specification,
batch/lot number, and manufacturer from the image. It can also suggest
allowlisted chemistry labels and storage constraints for a valid CAS, or
translate an unfamiliar chemistry question into a SMARTS *search plan*. Both
outputs remain editable and must be reviewed. RDKit validates and executes the
SMARTS plan against the real inventory; the model never reports stock
availability. The safety rule engine—not the model—chooses the recommended
storage location.

## Order data

Step 3 accepts a CSV export with `order_reference` (or `order_id`) and
`chemical_name` (or `name`). Optional supported columns are `cas_number`,
`catalog_number`, `specification`, `manufacturer`, `quantity`, and `unit`.
The importer is idempotent by order reference. Exact CAS conflicts are never
matched, and ambiguous candidates require a human selection.

## Storage and deployment

`inventory.db` is a local SQLite implementation suitable for development and a
single running process. Streamlit Community Cloud does **not** guarantee local
file persistence, so do not use this default database as the durable source of
truth for a real laboratory. Production deployment requires an externally
managed database and the relevant credentials; those are intentionally not
committed to this repository.


### Render

The repository includes a root-level `render.yaml` Blueprint for a free Render
web service. It installs `requirements.txt`, binds Streamlit to Render's `PORT`,
and exposes Streamlit's health endpoint. The initial service uses manual AI mode
so it can deploy without committing a provider key.

To enable Gemini after deployment, add `GEMINI_API_KEY` in the Render service's
Environment page and change `LABMIND_VISION_MODE` to `live`. Never commit the
key or a local `.streamlit/secrets.toml` file.

Free Render services use an ephemeral filesystem. For persistent SQLite data,
upgrade to a paid service, attach a disk at `/var/data`, and set
`LABMIND_DB_PATH=/var/data/inventory.db`. For multi-instance production use,
replace SQLite with an externally managed database.

Run the verification suite with:

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
```

## GitHub Pages

Pushes that change `site/` on the `frontend` branch deploy through
`.github/workflows/deploy-pages.yml`. The repository owner must select
**GitHub Actions** under **Settings → Pages → Build and deployment** once.

GitHub Pages hosts only the static browser build in `site/`. The operational
Python intake and inventory application is the Streamlit deployment from
`app.py` on the `frontend` branch.
