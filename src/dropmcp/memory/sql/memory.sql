-- Shared agent memory: reference Postgres schema for dropmcp.
--
-- dropmcp never runs DDL against Postgres. Apply this file with your migration
-- tool before enabling memory (DROPMCP_MEMORY=true). Table names are unqualified,
-- so it creates the tables in the first schema on the search_path. Every
-- statement is idempotent, and no extensions are needed.

CREATE TABLE IF NOT EXISTS memory (
    id                 TEXT PRIMARY KEY,
    key                TEXT NOT NULL UNIQUE,
    created_at         TIMESTAMPTZ NOT NULL,
    created_by         TEXT,
    server             TEXT NOT NULL,
    last_confirmed_at  TIMESTAMPTZ NOT NULL,
    kind               TEXT NOT NULL,
    title              TEXT NOT NULL,
    body               TEXT NOT NULL,
    evidence           TEXT,
    repo               TEXT,
    system             TEXT,
    language           TEXT,
    domain             TEXT,
    stack              TEXT[] NOT NULL DEFAULT '{}',
    task               TEXT,
    path               TEXT,
    status             TEXT NOT NULL DEFAULT 'active',
    superseded_by      TEXT REFERENCES memory (id),
    hidden_at          TIMESTAMPTZ,
    fingerprint        TEXT NOT NULL,
    occurrence_count   INTEGER NOT NULL DEFAULT 1,
    recall_count       INTEGER NOT NULL DEFAULT 0,
    promoted_url       TEXT,
    model              TEXT NOT NULL,
    client             TEXT,
    search_text        TSVECTOR GENERATED ALWAYS AS (
                           setweight(to_tsvector('english', title), 'A') ||
                           setweight(to_tsvector('english', body), 'B')) STORED,
    embedding          BYTEA,
    embedding_model    TEXT,
    embedding_dim      INTEGER
);

CREATE INDEX IF NOT EXISTS ix_memory_status_repo ON memory (status, repo);
CREATE INDEX IF NOT EXISTS ix_memory_status_language ON memory (status, language);
CREATE INDEX IF NOT EXISTS ix_memory_search_text ON memory USING GIN (search_text);
CREATE INDEX IF NOT EXISTS ix_memory_stack ON memory USING GIN (stack);
CREATE INDEX IF NOT EXISTS ix_memory_fingerprint ON memory (fingerprint);

CREATE TABLE IF NOT EXISTS memory_report (
    id                 TEXT PRIMARY KEY,
    created_at         TIMESTAMPTZ NOT NULL,
    last_seen_at       TIMESTAMPTZ NOT NULL,
    created_by         TEXT,
    client             TEXT,
    model              TEXT NOT NULL,
    memory_id          TEXT REFERENCES memory (id),
    reported_key       TEXT,
    described_memory   TEXT,
    candidate_keys     TEXT[] NOT NULL DEFAULT '{}',
    problem            TEXT NOT NULL,
    reason             TEXT,
    correction         TEXT,
    context            TEXT,
    fingerprint        TEXT NOT NULL,
    occurrence_count   INTEGER NOT NULL DEFAULT 1,
    status             TEXT NOT NULL DEFAULT 'open',
    resolved_at        TIMESTAMPTZ,
    resolution         TEXT
);

CREATE INDEX IF NOT EXISTS ix_memory_report_memory_id ON memory_report (memory_id);
CREATE INDEX IF NOT EXISTS ix_memory_report_fingerprint ON memory_report (fingerprint);

CREATE TABLE IF NOT EXISTS memory_recall_log (
    id                 TEXT PRIMARY KEY,
    created_at         TIMESTAMPTZ NOT NULL,
    created_by         TEXT,
    server             TEXT NOT NULL,
    client             TEXT,
    context            TEXT,
    had_query          BOOLEAN NOT NULL,
    returned_ids       TEXT[] NOT NULL DEFAULT '{}',
    duration_ms        INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS memory_near_duplicate_log (
    id                 TEXT PRIMARY KEY,
    created_at         TIMESTAMPTZ NOT NULL,
    embedding_model    TEXT,
    threshold          DOUBLE PRECISION,
    top_similarity     DOUBLE PRECISION,
    choice             TEXT,
    fingerprint        TEXT,
    top_key            TEXT
);
