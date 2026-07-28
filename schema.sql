PRAGMA foreign_keys = ON;

-- One row represents one physical reagent lot or container.
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
