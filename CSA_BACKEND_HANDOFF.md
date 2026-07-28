# CSA Backend Handoff

This branch adds the first database-backed intake foundation without changing
the existing `app_v5.py` interface.

## Included

- Strict CAS format and check-digit validation
- Repeatable SQLite schema initialization
- Human-confirmed reagent insertion
- CAS-based lot lookup
- Newest-first inventory listing
- Focused unit tests for validation, schema, and database operations

## Public interfaces

```python
from backend.db_utils import insert_reagent, list_reagents, query_by_cas

record_id = insert_reagent(
    reagent_data,
    confirmed=True,
)
matching_lots = query_by_cas("64-17-5")
all_records = list_reagents()
```

`insert_reagent` rejects unconfirmed records, invalid CAS values, negative or
non-finite quantities, invalid dates, and malformed JSON list fields.

## Frontend payload mapping

| `app_v5.py` field | Database field |
| --- | --- |
| `chemical_name` | `name` |
| `cas_number` | `cas_number` |
| `specification` | `specification` |
| `batch_number` | `lot_number` |
| `manufacturer` | `manufacturer` |
| `expiry_date` | `expiry_date` |
| `quantity` | `quantity` |
| `unit` | `quantity_unit` |
| `chemical_labels` | `chemical_tags` |
| `storage_constraints` | `hazard_labels` |
| `storage_location` | `storage_suggestion` |
| `storage_rule` | `storage_reason` |

The frontend's `storage_reviewed` means that review is complete, while the
database's `manual_review` indicates that review is still required. Do not map
these fields without accounting for the inverse meaning.

The revised MVP does not persist `pending_order`. Extraction and classification
confidence fields are also not yet stored by this phase.

## Validation

Run the focused backend tests:

```powershell
python -m unittest tests.test_cas_validator tests.test_db_init tests.test_db_utils -v
```

The generated `inventory.db` is local development state and is ignored by Git.
A persistent hosted database will still be required for public deployment.

## Integration note

The current frontend test suite intentionally checks that `app_v5.py` does not
import backend modules. CS B should update that test when the UI is connected
to `insert_reagent`, `query_by_cas`, and `list_reagents`.
