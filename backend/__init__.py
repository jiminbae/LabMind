"""CSA CAS validation and durable local intake database package."""

from .cas_validator import (
    CASValidationResult,
    is_valid_cas,
    validate_cas,
    validate_cas_details,
)
from .classification_cache import (
    ClassificationCacheValidationError,
    get_cas_classification,
    upsert_cas_classification,
)
from .db_init import (
    DATABASE_SCHEMA_VERSION,
    DatabaseMigrationError,
    get_schema_version,
    init_db,
    resolve_db_path,
)
from .db_utils import (
    IntakeConflictError,
    ReagentValidationError,
    insert_reagent,
    list_reagents,
    query_by_cas,
)
from .intake_service import IntakeServiceError, map_intake_payload, register_intake
from .order_matching import (
    PendingOrderConflictError,
    PendingOrderValidationError,
    create_pending_order,
    import_pending_orders,
    list_pending_orders,
    mark_order_received,
    match_pending_orders,
    select_unique_order_match,
)
from .query_translation_service import (
    ChemicalQueryTranslation,
    QueryTranslationResult,
    translate_chemical_question,
)

__all__ = [
    "CASValidationResult",
    "ChemicalQueryTranslation",
    "ClassificationCacheValidationError",
    "DATABASE_SCHEMA_VERSION",
    "DatabaseMigrationError",
    "IntakeConflictError",
    "IntakeServiceError",
    "PendingOrderConflictError",
    "PendingOrderValidationError",
    "QueryTranslationResult",
    "ReagentValidationError",
    "create_pending_order",
    "get_cas_classification",
    "get_schema_version",
    "import_pending_orders",
    "init_db",
    "insert_reagent",
    "is_valid_cas",
    "list_pending_orders",
    "list_reagents",
    "map_intake_payload",
    "mark_order_received",
    "match_pending_orders",
    "query_by_cas",
    "register_intake",
    "resolve_db_path",
    "select_unique_order_match",
    "translate_chemical_question",
    "upsert_cas_classification",
    "validate_cas",
    "validate_cas_details",
]
