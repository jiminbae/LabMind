# OCR Failure Log — Prompt 1.0

Test set: five reagent-label images processed through the configured live vision provider. Full structured outputs are stored in `outputs/`.

## Summary

- Images tested: 5
- Full pipeline successes: 2
- Expected missing-catalog failures: 2
- Pending manual source-label review: 1
- Reviewed catalog-number decisions correct: 4 of 4

The backend intentionally stops inventory and recommendation lookup when a catalog number is not visible. After the parser update, it still preserves any recognized lot number, expiry date, brand, product name, and confidence value.

## Failure cases

### Image 1 — PBS 10X

- Status: `failed`
- Cause: no catalog number is visible on the label
- Retained fields: lot `7439`, expiry `2017-09-30`, product `PBS 10X`
- Assessment: expected safe failure; the model did not invent a catalog number

### Image 2 — Hydrochloric Acid

- Status: `failed`
- Cause: the label shows CAS `7667-01-0`, but no catalog number
- Retained fields: lot `AC45739`, expiry `2026-10-31`, product `HYDROCHLORIC ACID`
- Assessment: expected safe failure; the CAS number was correctly not reused as a catalog number

### Image 3 — Alcohol

- Status: `failed`
- Cause: no catalog number was returned
- Retained fields: lot `0001234`, expiry `2026-09-13`, product `ALCOHOL`
- Assessment: source-label review is still required before counting this row in accuracy

## Non-OCR data gaps

Images 4 and 5 produced valid catalog numbers (`156248-100G` and `270741-2L`), but those catalogs are not present in the current sample `inventory.csv` or `products.csv`. The pipeline therefore returns `found: false`; this is a dataset-coverage limitation rather than an OCR failure.

## Fix implemented

`backend/vision_service.py` now returns a failed `OCRResult` with all available partial fields when the catalog number is missing. This lets the Streamlit UI show useful recognized data while preventing unsafe inventory matching.
