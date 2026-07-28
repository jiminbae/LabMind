PRAGMA foreign_keys = ON;

-- `init_db` records applied versions in this table.  The table is intentionally
-- small: it is a local audit trail for additive SQLite migrations, not a
-- replacement for a hosted database migration service.
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- One row represents one physical reagent lot or container.  `receipt_key`
-- and `intake_id` are optional because legacy callers may still create a
-- record without an upstream receipt.  When either is supplied, db_utils
-- makes the intake idempotent and indexes enforce that invariant.
CREATE TABLE IF NOT EXISTS reagents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    cas_number TEXT NOT NULL,
    catalog_number TEXT,
    specification TEXT,
    lot_number TEXT,
    manufacturer TEXT,
    quantity REAL NOT NULL DEFAULT 0 CHECK (quantity >= 0),
    quantity_unit TEXT NOT NULL DEFAULT 'unit',
    location TEXT,
    expiry_date DATE,
    smiles TEXT,
    chemical_tags TEXT NOT NULL DEFAULT '[]',
    hazard_labels TEXT NOT NULL DEFAULT '[]',
    storage_suggestion TEXT,
    storage_reason TEXT,
    manual_review INTEGER NOT NULL DEFAULT 1
        CHECK (manual_review IN (0, 1)),
    receipt_key TEXT,
    intake_id TEXT,
    order_reference TEXT,
    match_score REAL CHECK (
        match_score IS NULL OR (match_score >= 0 AND match_score <= 1)
    ),
    image_signature TEXT,
    extraction_confidence REAL CHECK (
        extraction_confidence IS NULL OR (
            extraction_confidence >= 0 AND extraction_confidence <= 1
        )
    ),
    extraction_source TEXT,
    extraction_rationale TEXT,
    classification_confidence REAL CHECK (
        classification_confidence IS NULL OR (
            classification_confidence >= 0 AND classification_confidence <= 1
        )
    ),
    classification_source TEXT,
    classification_rationale TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_reagents_cas_number
    ON reagents (cas_number);

CREATE INDEX IF NOT EXISTS idx_reagents_name
    ON reagents (name);

CREATE INDEX IF NOT EXISTS idx_reagents_catalog_number
    ON reagents (catalog_number);

-- Deterministic mappings produce suggestions only; a user must confirm storage.
CREATE TABLE IF NOT EXISTS storage_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    hazard_label TEXT UNIQUE NOT NULL,
    suggested_location TEXT NOT NULL,
    reason TEXT NOT NULL,
    priority INTEGER NOT NULL DEFAULT 100,
    requires_manual_review INTEGER NOT NULL DEFAULT 1
        CHECK (requires_manual_review IN (0, 1))
);

INSERT OR IGNORE INTO storage_rules (
    hazard_label,
    suggested_location,
    reason,
    priority,
    requires_manual_review
) VALUES
    (
        'flammable',
        'flammable_cabinet',
        'Flammable label detected; confirm against the SDS before storage.',
        10,
        1
    ),
    (
        'oxidizer',
        'oxidizer_cabinet',
        'Oxidizer label detected; keep incompatible fuels and reducers separate.',
        20,
        1
    ),
    (
        'corrosive',
        'corrosive_cabinet',
        'Corrosive label detected; confirm acid/base compatibility and ventilation.',
        30,
        1
    ),
    (
        'toxic',
        'secure_toxic_storage',
        'Toxic label detected; use controlled storage after human review.',
        40,
        1
    );

-- Chemistry labels are cached by CAS number.  This cache records a reviewed
-- chemistry description; it never assigns a physical cabinet directly.
CREATE TABLE IF NOT EXISTS cas_classification_cache (
    cas_number TEXT PRIMARY KEY,
    chemical_tags TEXT NOT NULL DEFAULT '[]',
    hazard_labels TEXT NOT NULL DEFAULT '[]',
    confidence REAL CHECK (
        confidence IS NULL OR (confidence >= 0 AND confidence <= 1)
    ),
    source TEXT NOT NULL DEFAULT 'manual',
    rationale TEXT,
    smiles TEXT,
    reviewed INTEGER NOT NULL DEFAULT 0 CHECK (reviewed IN (0, 1)),
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Local staging area for orders waiting to be received.  Order synchronization
-- remains an adapter concern; this table deliberately does not scrape or call
-- external purchasing systems.
CREATE TABLE IF NOT EXISTS pending_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_reference TEXT NOT NULL,
    name TEXT NOT NULL,
    cas_number TEXT,
    catalog_number TEXT,
    specification TEXT,
    manufacturer TEXT,
    quantity REAL NOT NULL DEFAULT 0 CHECK (quantity >= 0),
    quantity_unit TEXT NOT NULL DEFAULT 'unit',
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'matched', 'received', 'cancelled')),
    received_reagent_id INTEGER REFERENCES reagents(id) ON DELETE SET NULL,
    received_at DATETIME,
    source TEXT,
    raw_payload TEXT NOT NULL DEFAULT '{}',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);
