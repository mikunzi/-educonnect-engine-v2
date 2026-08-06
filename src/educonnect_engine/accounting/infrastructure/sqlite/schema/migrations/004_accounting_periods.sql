CREATE TABLE accounting_periods (
    id TEXT PRIMARY KEY CHECK (id <> ''),
    legal_entity_id TEXT NOT NULL CHECK (legal_entity_id <> ''),
    fiscal_year INTEGER NOT NULL,
    start_date TEXT NOT NULL CHECK (start_date <> ''),
    end_date TEXT NOT NULL CHECK (end_date <> ''),
    status TEXT NOT NULL CHECK (status <> ''),
    version INTEGER NOT NULL CHECK (version >= 0),
    CHECK (end_date >= start_date)
);

CREATE INDEX idx_accounting_periods_scope_status
ON accounting_periods(legal_entity_id, fiscal_year, status);

CREATE INDEX idx_accounting_periods_scope_dates
ON accounting_periods(legal_entity_id, fiscal_year, start_date, end_date);