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

- Label intake with local CAS check-digit validation
- Pending-order candidate review
- CAS-level, multi-label chemical function classification
- Deterministic, fail-closed storage assignment rules
- Structured inventory questions compiled to bound SQL plans
- Chemical-meaning questions translated to validated SMARTS and matched with
  RDKit before joining to on-hand inventory

The language layer never determines whether an item is in stock. Availability,
quantity, expiry state, registration IDs, and storage locations remain
deterministic inventory or rule-engine decisions.

## Integration boundaries

The deployed frontend currently uses a local inventory snapshot and reviewed
chemistry translation catalog. Production adapters are still required for the
VLM extraction provider, ordering-system API, chemistry model, and inventory
database.

## GitHub Pages

Pushes that change `site/` on the `frontend` branch deploy through
`.github/workflows/deploy-pages.yml`. The repository owner must select
**GitHub Actions** under **Settings → Pages → Build and deployment** once.
