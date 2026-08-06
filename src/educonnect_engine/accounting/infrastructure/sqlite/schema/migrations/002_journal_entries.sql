CREATE TABLE journal_entries (
    id TEXT PRIMARY KEY,
    legal_entity_id TEXT NOT NULL,
    fiscal_year INTEGER NOT NULL,
    journal_code TEXT NOT NULL,
    entry_number TEXT NOT NULL,
    posting_date TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status <> ''),
    posted_at TEXT NULL,
    currency TEXT NOT NULL CHECK (currency <> ''),
    version INTEGER NOT NULL CHECK (version >= 0),
    source_entry_id TEXT NULL,
    correction_reason TEXT NULL,
    FOREIGN KEY (source_entry_id) REFERENCES journal_entries(id),
    CHECK (
        (source_entry_id IS NULL AND correction_reason IS NULL)
        OR (source_entry_id IS NOT NULL AND correction_reason IS NOT NULL)
    )
);

CREATE INDEX idx_journal_entries_source_entry_id
ON journal_entries(source_entry_id);

CREATE TABLE journal_entry_lines (
    entry_id TEXT NOT NULL,
    position INTEGER NOT NULL CHECK (position >= 0),
    account_number TEXT NOT NULL,
    side TEXT NOT NULL CHECK (side IN ('debit', 'credit')),
    amount TEXT NOT NULL,
    currency TEXT NOT NULL CHECK (currency <> ''),
    description TEXT NOT NULL,
    PRIMARY KEY (entry_id, position),
    FOREIGN KEY (entry_id) REFERENCES journal_entries(id) ON DELETE CASCADE
);
