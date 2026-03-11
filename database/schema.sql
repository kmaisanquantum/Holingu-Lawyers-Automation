-- ============================================================
--  HOLINGU LAWYERS ANALYTICAL REPOSITORY
--  Vault Database Schema — SQLite / PostgreSQL compatible
--  Port Moresby, Papua New Guinea
--  Version: 1.0  |  March 2026
-- ============================================================
--
--  TABLES (13 total):
--    1. users                 – Firm personnel & roles
--    2. clients               – Client registry (IPA / TIN)
--    3. matters               – Top-level matter container
--    4. documents             – Document vault with versioning
--    5. property_references   – State Lease / Mining Lease refs
--    6. extracted_parties     – AI-extracted party names & roles
--    7. extracted_financials  – AI-extracted financial terms
--    8. extracted_dates       – Deadlines & sunset clauses
--    9. risk_flags            – AI clause risk classification
--   10. generated_documents   – Drafter output + approval flow
--   11. document_embeddings   – Vector store index metadata
--   12. audit_log             – Immutable activity trail
--   13. matter_notes          – Privileged attendance notes
--
--  All currency values are in PGK (Papua New Guinean Kina)
--  Governing law: Laws of Papua New Guinea
-- ============================================================

PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

-- ── 1. USERS ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    email           TEXT    NOT NULL UNIQUE,
    full_name       TEXT    NOT NULL,
    display_name    TEXT    NOT NULL,
    role            TEXT    NOT NULL CHECK(role IN (
                        'senior_partner','partner','associate',
                        'paralegal','admin')),
    admission_no    TEXT,               -- PNG Bar Council admission number
    tin             TEXT,               -- Tax Identification Number (IRC)
    phone           TEXT,
    is_active       INTEGER NOT NULL DEFAULT 1,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- ── 2. CLIENTS ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS clients (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    client_code     TEXT    NOT NULL UNIQUE,    -- e.g. CLT-001
    name            TEXT    NOT NULL,
    client_type     TEXT    NOT NULL CHECK(client_type IN (
                        'individual','company','government','ngo')),
    ipa_reg_no      TEXT,               -- Investment Promotion Authority Reg No.
    tin             TEXT,               -- Internal Revenue Commission TIN
    address         TEXT,
    city            TEXT    DEFAULT 'Port Moresby',
    province        TEXT    DEFAULT 'NCD',
    country         TEXT    DEFAULT 'Papua New Guinea',
    contact_name    TEXT,
    contact_email   TEXT,
    contact_phone   TEXT,
    notes           TEXT,
    is_active       INTEGER NOT NULL DEFAULT 1,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- ── 3. MATTERS ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS matters (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    matter_ref      TEXT    NOT NULL UNIQUE,    -- e.g. HLG-2024-001
    title           TEXT    NOT NULL,
    matter_type     TEXT    NOT NULL CHECK(matter_type IN (
                        'deed','deal','contract','litigation',
                        'advisory','mining','employment')),
    status          TEXT    NOT NULL DEFAULT 'active' CHECK(status IN (
                        'active','on_hold','closed','archived')),
    value_pgk       REAL,                       -- Matter value in PGK
    value_currency  TEXT    DEFAULT 'PGK',
    description     TEXT,
    governing_law   TEXT    DEFAULT 'Laws of Papua New Guinea',
    court_tribunal  TEXT,                       -- For litigation matters
    client_id       INTEGER REFERENCES clients(id) ON DELETE SET NULL,
    lead_partner_id INTEGER REFERENCES users(id)   ON DELETE SET NULL,
    opened_date     TEXT    NOT NULL DEFAULT (date('now')),
    closed_date     TEXT,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- ── 4. DOCUMENTS ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS documents (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    matter_id       INTEGER NOT NULL REFERENCES matters(id) ON DELETE CASCADE,
    doc_ref         TEXT    NOT NULL UNIQUE,    -- e.g. DOC-2024-0001
    filename        TEXT    NOT NULL,           -- Stored filename (slug)
    original_name   TEXT    NOT NULL,           -- Original upload filename
    doc_type        TEXT    NOT NULL CHECK(doc_type IN (
                        'deed','agreement','lease','correspondence',
                        'court_filing','certificate','other')),
    version         INTEGER NOT NULL DEFAULT 1,
    page_count      INTEGER,
    file_size_kb    INTEGER,
    mime_type       TEXT    DEFAULT 'application/pdf',
    storage_path    TEXT,                       -- S3 / object storage path
    checksum_sha256 TEXT,                       -- File integrity hash
    analysis_status TEXT    NOT NULL DEFAULT 'pending' CHECK(analysis_status IN (
                        'pending','processing','analysed','failed','archived')),
    is_executed     INTEGER NOT NULL DEFAULT 0,
    execution_date  TEXT,
    uploaded_by     INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- ── 5. PROPERTY REFERENCES ────────────────────────────────────────────────
--  Stores PNG-specific land / lease references for each matter
CREATE TABLE IF NOT EXISTS property_references (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    matter_id       INTEGER NOT NULL REFERENCES matters(id) ON DELETE CASCADE,
    ref_type        TEXT    NOT NULL CHECK(ref_type IN (
                        'state_lease','customary_land','freehold',
                        'mining_lease','forest_clearance')),
    volume          TEXT,               -- State Lease Volume number
    folio           TEXT,               -- State Lease Folio number
    lease_no        TEXT,               -- e.g. SL 2019/001 or ML 157
    land_name       TEXT,               -- Colloquial or registered name
    location        TEXT,
    province        TEXT,
    area_hectares   REAL,
    lease_expiry    TEXT,
    lessor          TEXT    DEFAULT 'Independent State of Papua New Guinea',
    notes           TEXT,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- ── 6. EXTRACTED PARTIES ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS extracted_parties (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id     INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    party_role      TEXT    NOT NULL,   -- e.g. Vendor, Purchaser, Lessee
    party_name      TEXT    NOT NULL,
    party_type      TEXT    CHECK(party_type IN (
                        'individual','company','government','ngo')),
    ipa_reg_no      TEXT,
    tin             TEXT,
    address         TEXT,
    ai_confidence   REAL    CHECK(ai_confidence BETWEEN 0 AND 1),
    is_verified     INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- ── 7. EXTRACTED FINANCIALS ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS extracted_financials (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id     INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    financial_type  TEXT    NOT NULL,   -- consideration, stamp_duty, bond, royalty, penalty
    label           TEXT    NOT NULL,   -- Human-readable label
    amount          REAL,               -- Absolute amount in PGK (or NULL if rate only)
    currency        TEXT    DEFAULT 'PGK',
    rate_pct        REAL,               -- Percentage rate (e.g. 5.0 for 5%)
    detail          TEXT,               -- Contextual note from clause
    ai_confidence   REAL    CHECK(ai_confidence BETWEEN 0 AND 1),
    is_verified     INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- ── 8. EXTRACTED DATES & DEADLINES ────────────────────────────────────────
CREATE TABLE IF NOT EXISTS extracted_dates (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id     INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    matter_id       INTEGER REFERENCES matters(id) ON DELETE CASCADE,
    date_type       TEXT    NOT NULL CHECK(date_type IN (
                        'completion','sunset','option','payment',
                        'milestone','expiry','filing','hearing','other')),
    label           TEXT    NOT NULL,
    due_date        TEXT    NOT NULL,   -- ISO 8601: YYYY-MM-DD
    clause_ref      TEXT,               -- e.g. Cl. 8.1
    alert_days_before INTEGER DEFAULT 14,
    alert_sent      INTEGER NOT NULL DEFAULT 0,
    is_critical     INTEGER NOT NULL DEFAULT 0,
    notes           TEXT,
    ai_confidence   REAL    CHECK(ai_confidence BETWEEN 0 AND 1),
    created_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- ── 9. RISK FLAGS ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS risk_flags (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id     INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    matter_id       INTEGER REFERENCES matters(id) ON DELETE CASCADE,
    flag_type       TEXT    NOT NULL CHECK(flag_type IN (
                        'unlimited_liability','unusual_indemnity',
                        'one_sided_termination','missing_clause',
                        'non_standard_governing_law','unfair_penalty',
                        'missing_force_majeure','dispute_resolution_gap',
                        'warranty_breach_risk','customary_land_issue','other')),
    severity        TEXT    NOT NULL CHECK(severity IN (
                        'low','medium','high','critical')),
    clause_ref      TEXT,
    description     TEXT    NOT NULL,
    recommendation  TEXT,
    status          TEXT    NOT NULL DEFAULT 'open' CHECK(status IN (
                        'open','reviewed','resolved','accepted')),
    reviewed_by     INTEGER REFERENCES users(id) ON DELETE SET NULL,
    reviewed_at     TEXT,
    ai_confidence   REAL    CHECK(ai_confidence BETWEEN 0 AND 1),
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- ── 10. GENERATED DOCUMENTS (Drafter Output) ──────────────────────────────
CREATE TABLE IF NOT EXISTS generated_documents (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    matter_id       INTEGER REFERENCES matters(id) ON DELETE SET NULL,
    template_type   TEXT    NOT NULL,   -- state_lease_transfer, sale_purchase, etc.
    doc_ref         TEXT    NOT NULL UNIQUE,    -- e.g. GEN-2024-0001
    filename        TEXT    NOT NULL,
    version         INTEGER NOT NULL DEFAULT 1,
    status          TEXT    NOT NULL DEFAULT 'draft' CHECK(status IN (
                        'draft','under_review','approved','executed','archived')),
    governing_law   TEXT    DEFAULT 'Laws of Papua New Guinea',
    parties_json    TEXT,               -- JSON: party details used at generation
    financials_json TEXT,               -- JSON: financial terms used
    config_json     TEXT,               -- JSON: full generation configuration
    generated_by    INTEGER REFERENCES users(id) ON DELETE SET NULL,
    approved_by     INTEGER REFERENCES users(id) ON DELETE SET NULL,
    approved_at     TEXT,
    storage_path    TEXT,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- ── 11. DOCUMENT EMBEDDINGS ───────────────────────────────────────────────
--  Metadata for vector index (pgvector or Pinecone)
CREATE TABLE IF NOT EXISTS document_embeddings (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id     INTEGER NOT NULL UNIQUE REFERENCES documents(id) ON DELETE CASCADE,
    model_used      TEXT    DEFAULT 'text-embedding-3-large',
    vector_dims     INTEGER DEFAULT 1536,
    chunk_count     INTEGER,
    index_name      TEXT    DEFAULT 'holingu-vault',
    embedding_status TEXT   NOT NULL DEFAULT 'pending' CHECK(embedding_status IN (
                        'pending','processing','indexed','failed')),
    indexed_at      TEXT,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- ── 12. AUDIT LOG ─────────────────────────────────────────────────────────
--  Immutable activity trail — no UPDATE/DELETE triggers on this table
CREATE TABLE IF NOT EXISTS audit_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER REFERENCES users(id) ON DELETE SET NULL,
    action          TEXT    NOT NULL,   -- CREATE | READ | UPDATE | DELETE | UPLOAD | GENERATE
    entity_type     TEXT    NOT NULL,   -- matter | document | risk_flag | client | etc.
    entity_id       INTEGER,
    entity_ref      TEXT,               -- Human-readable ref (HLG-2024-001)
    detail          TEXT,
    ip_address      TEXT,
    user_agent      TEXT,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- ── 13. MATTER NOTES ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS matter_notes (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    matter_id       INTEGER NOT NULL REFERENCES matters(id) ON DELETE CASCADE,
    author_id       INTEGER REFERENCES users(id) ON DELETE SET NULL,
    note_type       TEXT    DEFAULT 'general' CHECK(note_type IN (
                        'general','correspondence','advice','attendance','billing')),
    content         TEXT    NOT NULL,
    is_privileged   INTEGER NOT NULL DEFAULT 1,   -- Legal professional privilege flag
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- ══════════════════════════════════════════════════════════
--  INDEXES
-- ══════════════════════════════════════════════════════════
CREATE INDEX IF NOT EXISTS idx_matters_ref        ON matters(matter_ref);
CREATE INDEX IF NOT EXISTS idx_matters_status     ON matters(status);
CREATE INDEX IF NOT EXISTS idx_matters_type       ON matters(matter_type);
CREATE INDEX IF NOT EXISTS idx_matters_client     ON matters(client_id);
CREATE INDEX IF NOT EXISTS idx_matters_partner    ON matters(lead_partner_id);
CREATE INDEX IF NOT EXISTS idx_documents_matter   ON documents(matter_id);
CREATE INDEX IF NOT EXISTS idx_documents_status   ON documents(analysis_status);
CREATE INDEX IF NOT EXISTS idx_documents_type     ON documents(doc_type);
CREATE INDEX IF NOT EXISTS idx_dates_due          ON extracted_dates(due_date);
CREATE INDEX IF NOT EXISTS idx_dates_critical     ON extracted_dates(is_critical);
CREATE INDEX IF NOT EXISTS idx_dates_alert        ON extracted_dates(alert_sent, due_date);
CREATE INDEX IF NOT EXISTS idx_risks_severity     ON risk_flags(severity);
CREATE INDEX IF NOT EXISTS idx_risks_status       ON risk_flags(status);
CREATE INDEX IF NOT EXISTS idx_risks_matter       ON risk_flags(matter_id);
CREATE INDEX IF NOT EXISTS idx_audit_entity       ON audit_log(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_audit_user         ON audit_log(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_date         ON audit_log(created_at);
CREATE INDEX IF NOT EXISTS idx_notes_matter       ON matter_notes(matter_id);
CREATE INDEX IF NOT EXISTS idx_embeddings_doc     ON document_embeddings(document_id);

-- ══════════════════════════════════════════════════════════
--  USEFUL VIEWS
-- ══════════════════════════════════════════════════════════

-- Active matters with client and partner names
CREATE VIEW IF NOT EXISTS v_matters_active AS
SELECT
    m.matter_ref,
    m.title,
    m.matter_type,
    m.status,
    m.value_pgk,
    m.governing_law,
    c.name          AS client_name,
    c.ipa_reg_no    AS client_ipa,
    u.display_name  AS lead_partner,
    m.opened_date,
    (SELECT COUNT(*) FROM documents d WHERE d.matter_id = m.id) AS doc_count,
    (SELECT COUNT(*) FROM risk_flags r WHERE r.matter_id = m.id AND r.status='open') AS open_risks
FROM matters m
LEFT JOIN clients c ON c.id = m.client_id
LEFT JOIN users   u ON u.id = m.lead_partner_id
WHERE m.status = 'active';

-- Critical upcoming deadlines (next 60 days)
CREATE VIEW IF NOT EXISTS v_critical_deadlines AS
SELECT
    ed.label,
    ed.due_date,
    ed.date_type,
    ed.clause_ref,
    ed.alert_days_before,
    ed.is_critical,
    m.matter_ref,
    m.title         AS matter_title,
    d.original_name AS source_document
FROM extracted_dates ed
JOIN matters   m ON m.id = ed.matter_id
JOIN documents d ON d.id = ed.document_id
WHERE ed.due_date >= date('now')
  AND ed.due_date <= date('now', '+60 days')
ORDER BY ed.due_date ASC;

-- Open risk flags by severity
CREATE VIEW IF NOT EXISTS v_risk_dashboard AS
SELECT
    rf.severity,
    rf.flag_type,
    rf.clause_ref,
    rf.description,
    rf.recommendation,
    rf.status,
    m.matter_ref,
    m.title         AS matter_title,
    d.original_name AS source_document,
    rf.ai_confidence,
    rf.created_at
FROM risk_flags rf
JOIN matters   m ON m.id = rf.matter_id
JOIN documents d ON d.id = rf.document_id
WHERE rf.status = 'open'
ORDER BY
    CASE rf.severity
        WHEN 'critical' THEN 1
        WHEN 'high'     THEN 2
        WHEN 'medium'   THEN 3
        ELSE 4
    END;

-- Document analysis pipeline status
CREATE VIEW IF NOT EXISTS v_doc_pipeline AS
SELECT
    d.doc_ref,
    d.original_name,
    d.doc_type,
    d.page_count,
    d.analysis_status,
    de.embedding_status,
    de.chunk_count,
    de.indexed_at,
    m.matter_ref,
    u.display_name  AS uploaded_by
FROM documents d
LEFT JOIN document_embeddings de ON de.document_id = d.id
LEFT JOIN matters m ON m.id = d.matter_id
LEFT JOIN users   u ON u.id = d.uploaded_by
ORDER BY d.created_at DESC;

-- ══════════════════════════════════════════════════════════
--  SAMPLE QUERIES
-- ══════════════════════════════════════════════════════════

-- Q1: All open matters with total value
-- SELECT matter_type, COUNT(*) as count, SUM(value_pgk) as total_pgk
-- FROM matters WHERE status='active'
-- GROUP BY matter_type ORDER BY total_pgk DESC;

-- Q2: Deadlines in next 30 days
-- SELECT * FROM v_critical_deadlines WHERE due_date <= date('now','+30 days');

-- Q3: All critical and high risk flags
-- SELECT * FROM v_risk_dashboard WHERE severity IN ('critical','high');

-- Q4: Documents pending analysis
-- SELECT doc_ref, original_name, matter_ref FROM v_doc_pipeline
-- WHERE analysis_status IN ('pending','processing');

-- Q5: Full matter view — HLG-2024-001
-- SELECT m.*, c.name as client, u.full_name as partner
-- FROM matters m
-- JOIN clients c ON c.id=m.client_id
-- JOIN users u ON u.id=m.lead_partner_id
-- WHERE m.matter_ref='HLG-2024-001';
