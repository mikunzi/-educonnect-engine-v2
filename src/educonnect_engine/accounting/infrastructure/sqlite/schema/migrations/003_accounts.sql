CREATE TABLE accounts (
    account_number TEXT PRIMARY KEY CHECK (account_number <> ''),
    name TEXT NOT NULL CHECK (name <> ''),
    category TEXT NOT NULL CHECK (category <> ''),
    classification TEXT NOT NULL CHECK (classification <> ''),
    is_active INTEGER NOT NULL CHECK (is_active IN (0, 1))
);