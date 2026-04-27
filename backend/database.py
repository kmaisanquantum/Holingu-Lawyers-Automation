"""
Database — SQLAlchemy for SQLite/PostgreSQL
Holingu Lawyers Vault, Port Moresby PNG
"""

import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
from typing import Generator

# Use absolute paths relative to this file's location for SQLite
_here = os.path.dirname(os.path.abspath(__file__))
_sqlite_path = os.path.normpath(os.path.join(_here, "database", "holingu_vault.db"))
_default_db_url = f"sqlite:///{_sqlite_path}"

# Render provides DATABASE_URL for PostgreSQL
DATABASE_URL = os.environ.get("DATABASE_URL", _default_db_url)

# Handle potential 'postgres://' vs 'postgresql://' for SQLAlchemy
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """Create all tables and seed data if database is fresh."""

    # Ensure local directory for SQLite exists
    if DATABASE_URL.startswith("sqlite"):
        db_dir = os.path.dirname(_sqlite_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

    is_sqlite = DATABASE_URL.startswith("sqlite")

    with engine.begin() as conn:
        # 1. USERS
        if is_sqlite:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS users (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    email         TEXT NOT NULL UNIQUE,
                    full_name     TEXT NOT NULL,
                    display_name  TEXT NOT NULL,
                    password_hash TEXT,
                    role          TEXT NOT NULL CHECK(role IN ('senior_partner','partner','associate','paralegal','admin')),
                    admission_no  TEXT,
                    tin           TEXT,
                    phone         TEXT,
                    is_active     INTEGER NOT NULL DEFAULT 1,
                    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
                    updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
                )
            """))
        else:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS users (
                    id            SERIAL PRIMARY KEY,
                    email         TEXT NOT NULL UNIQUE,
                    full_name     TEXT NOT NULL,
                    display_name  TEXT NOT NULL,
                    password_hash TEXT,
                    role          TEXT NOT NULL CHECK(role IN ('senior_partner','partner','associate','paralegal','admin')),
                    admission_no  TEXT,
                    tin           TEXT,
                    phone         TEXT,
                    is_active     INTEGER NOT NULL DEFAULT 1,
                    created_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """))

        # 2. CLIENTS
        if is_sqlite:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS clients (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    client_code   TEXT NOT NULL UNIQUE,
                    name          TEXT NOT NULL,
                    client_type   TEXT NOT NULL CHECK(client_type IN ('individual','company','government','ngo')),
                    ipa_reg_no    TEXT,
                    tin           TEXT,
                    address       TEXT,
                    city          TEXT DEFAULT 'Port Moresby',
                    province      TEXT DEFAULT 'NCD',
                    country       TEXT DEFAULT 'Papua New Guinea',
                    contact_name  TEXT,
                    contact_email TEXT,
                    contact_phone TEXT,
                    notes         TEXT,
                    is_active     INTEGER NOT NULL DEFAULT 1,
                    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
                    updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
                )
            """))
        else:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS clients (
                    id            SERIAL PRIMARY KEY,
                    client_code   TEXT NOT NULL UNIQUE,
                    name          TEXT NOT NULL,
                    client_type   TEXT NOT NULL CHECK(client_type IN ('individual','company','government','ngo')),
                    ipa_reg_no    TEXT,
                    tin           TEXT,
                    address       TEXT,
                    city          TEXT DEFAULT 'Port Moresby',
                    province      TEXT DEFAULT 'NCD',
                    country       TEXT DEFAULT 'Papua New Guinea',
                    contact_name  TEXT,
                    contact_email TEXT,
                    contact_phone TEXT,
                    notes         TEXT,
                    is_active     INTEGER NOT NULL DEFAULT 1,
                    created_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """))

        # 3. MATTERS
        if is_sqlite:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS matters (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    matter_ref      TEXT NOT NULL UNIQUE,
                    title           TEXT NOT NULL,
                    matter_type     TEXT NOT NULL CHECK(matter_type IN ('deed','deal','contract','litigation','advisory','mining','employment')),
                    status          TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','on_hold','closed','archived')),
                    value_pgk       REAL,
                    value_currency  TEXT DEFAULT 'PGK',
                    description     TEXT,
                    governing_law   TEXT DEFAULT 'Laws of Papua New Guinea',
                    court_tribunal  TEXT,
                    client_id       INTEGER REFERENCES clients(id) ON DELETE SET NULL,
                    lead_partner_id INTEGER REFERENCES users(id)   ON DELETE SET NULL,
                    opened_date     TEXT NOT NULL DEFAULT (date('now')),
                    closed_date     TEXT,
                    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
                    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
                )
            """))
        else:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS matters (
                    id              SERIAL PRIMARY KEY,
                    matter_ref      TEXT NOT NULL UNIQUE,
                    title           TEXT NOT NULL,
                    matter_type     TEXT NOT NULL CHECK(matter_type IN ('deed','deal','contract','litigation','advisory','mining','employment')),
                    status          TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','on_hold','closed','archived')),
                    value_pgk       REAL,
                    value_currency  TEXT DEFAULT 'PGK',
                    description     TEXT,
                    governing_law   TEXT DEFAULT 'Laws of Papua New Guinea',
                    court_tribunal  TEXT,
                    client_id       INTEGER REFERENCES clients(id) ON DELETE SET NULL,
                    lead_partner_id INTEGER REFERENCES users(id)   ON DELETE SET NULL,
                    opened_date     DATE NOT NULL DEFAULT CURRENT_DATE,
                    closed_date     DATE,
                    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """))

        # 4. DOCUMENTS
        if is_sqlite:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS documents (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    matter_id       INTEGER NOT NULL REFERENCES matters(id) ON DELETE CASCADE,
                    doc_ref         TEXT NOT NULL UNIQUE,
                    filename        TEXT NOT NULL,
                    original_name   TEXT NOT NULL,
                    doc_type        TEXT NOT NULL CHECK(doc_type IN ('deed','agreement','lease','correspondence','court_filing','certificate','other')),
                    version         INTEGER NOT NULL DEFAULT 1,
                    page_count      INTEGER,
                    file_size_kb    INTEGER,
                    mime_type       TEXT DEFAULT 'application/pdf',
                    storage_path    TEXT,
                    checksum_sha256 TEXT,
                    analysis_status TEXT NOT NULL DEFAULT 'pending' CHECK(analysis_status IN ('pending','processing','analysed','failed','archived')),
                    is_executed     INTEGER NOT NULL DEFAULT 0,
                    execution_date  TEXT,
                    uploaded_by     INTEGER REFERENCES users(id) ON DELETE SET NULL,
                    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
                    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
                )
            """))
        else:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS documents (
                    id              SERIAL PRIMARY KEY,
                    matter_id       INTEGER NOT NULL REFERENCES matters(id) ON DELETE CASCADE,
                    doc_ref         TEXT NOT NULL UNIQUE,
                    filename        TEXT NOT NULL,
                    original_name   TEXT NOT NULL,
                    doc_type        TEXT NOT NULL CHECK(doc_type IN ('deed','agreement','lease','correspondence','court_filing','certificate','other')),
                    version         INTEGER NOT NULL DEFAULT 1,
                    page_count      INTEGER,
                    file_size_kb    INTEGER,
                    mime_type       TEXT DEFAULT 'application/pdf',
                    storage_path    TEXT,
                    checksum_sha256 TEXT,
                    analysis_status TEXT NOT NULL DEFAULT 'pending' CHECK(analysis_status IN ('pending','processing','analysed','failed','archived')),
                    is_executed     INTEGER NOT NULL DEFAULT 0,
                    execution_date  DATE,
                    uploaded_by     INTEGER REFERENCES users(id) ON DELETE SET NULL,
                    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """))

        # 5. RISK FLAGS
        if is_sqlite:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS risk_flags (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    document_id   INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                    matter_id     INTEGER REFERENCES matters(id) ON DELETE CASCADE,
                    flag_type     TEXT NOT NULL CHECK(flag_type IN (
                                      'unlimited_liability','unusual_indemnity','one_sided_termination',
                                      'missing_clause','non_standard_governing_law','unfair_penalty',
                                      'missing_force_majeure','dispute_resolution_gap',
                                      'warranty_breach_risk','customary_land_issue','other')),
                    severity      TEXT NOT NULL CHECK(severity IN ('low','medium','high','critical')),
                    clause_ref    TEXT,
                    description   TEXT NOT NULL,
                    recommendation TEXT,
                    status        TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open','reviewed','resolved','accepted')),
                    reviewed_by   INTEGER REFERENCES users(id) ON DELETE SET NULL,
                    reviewed_at   TEXT,
                    ai_confidence REAL CHECK(ai_confidence BETWEEN 0 AND 1),
                    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
                    updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
                )
            """))
        else:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS risk_flags (
                    id            SERIAL PRIMARY KEY,
                    document_id   INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                    matter_id     INTEGER REFERENCES matters(id) ON DELETE CASCADE,
                    flag_type     TEXT NOT NULL CHECK(flag_type IN (
                                      'unlimited_liability','unusual_indemnity','one_sided_termination',
                                      'missing_clause','non_standard_governing_law','unfair_penalty',
                                      'missing_force_majeure','dispute_resolution_gap',
                                      'warranty_breach_risk','customary_land_issue','other')),
                    severity      TEXT NOT NULL CHECK(severity IN ('low','medium','high','critical')),
                    clause_ref    TEXT,
                    description   TEXT NOT NULL,
                    recommendation TEXT,
                    status        TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open','reviewed','resolved','accepted')),
                    reviewed_by   INTEGER REFERENCES users(id) ON DELETE SET NULL,
                    reviewed_at   TIMESTAMP,
                    ai_confidence REAL CHECK(ai_confidence BETWEEN 0 AND 1),
                    created_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """))

        # 6. EXTRACTED DATES
        if is_sqlite:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS extracted_dates (
                    id                INTEGER PRIMARY KEY AUTOINCREMENT,
                    document_id       INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                    matter_id         INTEGER REFERENCES matters(id) ON DELETE CASCADE,
                    date_type         TEXT NOT NULL CHECK(date_type IN ('completion','sunset','option','payment','milestone','expiry','filing','hearing','other')),
                    label             TEXT NOT NULL,
                    due_date          TEXT NOT NULL,
                    clause_ref        TEXT,
                    alert_days_before INTEGER DEFAULT 14,
                    alert_sent        INTEGER NOT NULL DEFAULT 0,
                    is_critical       INTEGER NOT NULL DEFAULT 0,
                    notes             TEXT,
                    ai_confidence     REAL CHECK(ai_confidence BETWEEN 0 AND 1),
                    created_at        TEXT NOT NULL DEFAULT (datetime('now'))
                )
            """))
        else:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS extracted_dates (
                    id                SERIAL PRIMARY KEY,
                    document_id       INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                    matter_id         INTEGER REFERENCES matters(id) ON DELETE CASCADE,
                    date_type         TEXT NOT NULL CHECK(date_type IN ('completion','sunset','option','payment','milestone','expiry','filing','hearing','other')),
                    label             TEXT NOT NULL,
                    due_date          DATE NOT NULL,
                    clause_ref        TEXT,
                    alert_days_before INTEGER DEFAULT 14,
                    alert_sent        INTEGER NOT NULL DEFAULT 0,
                    is_critical       INTEGER NOT NULL DEFAULT 0,
                    notes             TEXT,
                    ai_confidence     REAL CHECK(ai_confidence BETWEEN 0 AND 1),
                    created_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """))

        # 7. PROPERTY REFERENCES
        if is_sqlite:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS property_references (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    matter_id     INTEGER NOT NULL REFERENCES matters(id) ON DELETE CASCADE,
                    ref_type      TEXT NOT NULL CHECK(ref_type IN ('state_lease','customary_land','freehold','mining_lease','forest_clearance')),
                    volume        TEXT,
                    folio         TEXT,
                    lease_no      TEXT,
                    land_name     TEXT,
                    location      TEXT,
                    province      TEXT,
                    area_hectares REAL,
                    lease_expiry  TEXT,
                    lessor        TEXT DEFAULT 'Independent State of Papua New Guinea',
                    notes         TEXT,
                    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
                )
            """))
        else:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS property_references (
                    id            SERIAL PRIMARY KEY,
                    matter_id     INTEGER NOT NULL REFERENCES matters(id) ON DELETE CASCADE,
                    ref_type      TEXT NOT NULL CHECK(ref_type IN ('state_lease','customary_land','freehold','mining_lease','forest_clearance')),
                    volume        TEXT,
                    folio         TEXT,
                    lease_no      TEXT,
                    land_name     TEXT,
                    location      TEXT,
                    province      TEXT,
                    area_hectares REAL,
                    lease_expiry  DATE,
                    lessor        TEXT DEFAULT 'Independent State of Papua New Guinea',
                    notes         TEXT,
                    created_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """))

        # 8. EXTRACTED PARTIES
        if is_sqlite:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS extracted_parties (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    document_id   INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                    party_role    TEXT NOT NULL,
                    party_name    TEXT NOT NULL,
                    party_type    TEXT CHECK(party_type IN ('individual','company','government','ngo')),
                    ipa_reg_no    TEXT,
                    tin           TEXT,
                    address       TEXT,
                    ai_confidence REAL CHECK(ai_confidence BETWEEN 0 AND 1),
                    is_verified   INTEGER NOT NULL DEFAULT 0,
                    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
                )
            """))
        else:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS extracted_parties (
                    id            SERIAL PRIMARY KEY,
                    document_id   INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                    party_role    TEXT NOT NULL,
                    party_name    TEXT NOT NULL,
                    party_type    TEXT CHECK(party_type IN ('individual','company','government','ngo')),
                    ipa_reg_no    TEXT,
                    tin           TEXT,
                    address       TEXT,
                    ai_confidence REAL CHECK(ai_confidence BETWEEN 0 AND 1),
                    is_verified   INTEGER NOT NULL DEFAULT 0,
                    created_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """))

        # 9. EXTRACTED FINANCIALS
        if is_sqlite:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS extracted_financials (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    document_id   INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                    financial_type TEXT NOT NULL,
                    label         TEXT NOT NULL,
                    amount        REAL,
                    currency      TEXT DEFAULT 'PGK',
                    rate_pct      REAL,
                    detail        TEXT,
                    ai_confidence REAL CHECK(ai_confidence BETWEEN 0 AND 1),
                    is_verified   INTEGER NOT NULL DEFAULT 0,
                    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
                )
            """))
        else:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS extracted_financials (
                    id            SERIAL PRIMARY KEY,
                    document_id   INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                    financial_type TEXT NOT NULL,
                    label         TEXT NOT NULL,
                    amount        REAL,
                    currency      TEXT DEFAULT 'PGK',
                    rate_pct      REAL,
                    detail        TEXT,
                    ai_confidence REAL CHECK(ai_confidence BETWEEN 0 AND 1),
                    is_verified   INTEGER NOT NULL DEFAULT 0,
                    created_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """))

        # 10. GENERATED DOCUMENTS
        if is_sqlite:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS generated_documents (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    matter_id       INTEGER REFERENCES matters(id) ON DELETE SET NULL,
                    template_type   TEXT NOT NULL,
                    doc_ref         TEXT NOT NULL UNIQUE,
                    filename        TEXT NOT NULL,
                    version         INTEGER NOT NULL DEFAULT 1,
                    status          TEXT NOT NULL DEFAULT 'draft' CHECK(status IN ('draft','under_review','approved','executed','archived')),
                    governing_law   TEXT DEFAULT 'Laws of Papua New Guinea',
                    parties_json    TEXT,
                    financials_json TEXT,
                    config_json     TEXT,
                    generated_by    INTEGER REFERENCES users(id) ON DELETE SET NULL,
                    approved_by     INTEGER REFERENCES users(id) ON DELETE SET NULL,
                    approved_at     TEXT,
                    storage_path    TEXT,
                    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
                    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
                )
            """))
        else:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS generated_documents (
                    id              SERIAL PRIMARY KEY,
                    matter_id       INTEGER REFERENCES matters(id) ON DELETE SET NULL,
                    template_type   TEXT NOT NULL,
                    doc_ref         TEXT NOT NULL UNIQUE,
                    filename        TEXT NOT NULL,
                    version         INTEGER NOT NULL DEFAULT 1,
                    status          TEXT NOT NULL DEFAULT 'draft' CHECK(status IN ('draft','under_review','approved','executed','archived')),
                    governing_law   TEXT DEFAULT 'Laws of Papua New Guinea',
                    parties_json    TEXT,
                    financials_json TEXT,
                    config_json     TEXT,
                    generated_by    INTEGER REFERENCES users(id) ON DELETE SET NULL,
                    approved_by     INTEGER REFERENCES users(id) ON DELETE SET NULL,
                    approved_at     TIMESTAMP,
                    storage_path    TEXT,
                    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """))

        # 11. DOCUMENT EMBEDDINGS
        if is_sqlite:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS document_embeddings (
                    id               INTEGER PRIMARY KEY AUTOINCREMENT,
                    document_id      INTEGER NOT NULL UNIQUE REFERENCES documents(id) ON DELETE CASCADE,
                    model_used       TEXT DEFAULT 'text-embedding-3-large',
                    vector_dims      INTEGER DEFAULT 1536,
                    chunk_count      INTEGER,
                    index_name       TEXT DEFAULT 'holingu-vault',
                    embedding_status TEXT NOT NULL DEFAULT 'pending' CHECK(embedding_status IN ('pending','processing','indexed','failed')),
                    indexed_at       TEXT,
                    created_at       TEXT NOT NULL DEFAULT (datetime('now'))
                )
            """))
        else:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS document_embeddings (
                    id               SERIAL PRIMARY KEY,
                    document_id      INTEGER NOT NULL UNIQUE REFERENCES documents(id) ON DELETE CASCADE,
                    model_used       TEXT DEFAULT 'text-embedding-3-large',
                    vector_dims      INTEGER DEFAULT 1536,
                    chunk_count      INTEGER,
                    index_name       TEXT DEFAULT 'holingu-vault',
                    embedding_status TEXT NOT NULL DEFAULT 'pending' CHECK(embedding_status IN ('pending','processing','indexed','failed')),
                    indexed_at       TIMESTAMP,
                    created_at       TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """))

        # 12. AUDIT LOG
        if is_sqlite:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS audit_log (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id     INTEGER REFERENCES users(id) ON DELETE SET NULL,
                    action      TEXT NOT NULL,
                    entity_type TEXT NOT NULL,
                    entity_id   INTEGER,
                    entity_ref  TEXT,
                    detail      TEXT,
                    ip_address  TEXT,
                    user_agent  TEXT,
                    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
                )
            """))
        else:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS audit_log (
                    id          SERIAL PRIMARY KEY,
                    user_id     INTEGER REFERENCES users(id) ON DELETE SET NULL,
                    action      TEXT NOT NULL,
                    entity_type TEXT NOT NULL,
                    entity_id   INTEGER,
                    entity_ref  TEXT,
                    detail      TEXT,
                    ip_address  TEXT,
                    user_agent  TEXT,
                    created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """))

        # 13. MATTER NOTES
        if is_sqlite:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS matter_notes (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    matter_id    INTEGER NOT NULL REFERENCES matters(id) ON DELETE CASCADE,
                    author_id    INTEGER REFERENCES users(id) ON DELETE SET NULL,
                    note_type    TEXT DEFAULT 'general' CHECK(note_type IN ('general','correspondence','advice','attendance','billing')),
                    content      TEXT NOT NULL,
                    is_privileged INTEGER NOT NULL DEFAULT 1,
                    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
                    updated_at   TEXT NOT NULL DEFAULT (datetime('now'))
                )
            """))
        else:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS matter_notes (
                    id           SERIAL PRIMARY KEY,
                    matter_id    INTEGER NOT NULL REFERENCES matters(id) ON DELETE CASCADE,
                    author_id    INTEGER REFERENCES users(id) ON DELETE SET NULL,
                    note_type    TEXT DEFAULT 'general' CHECK(note_type IN ('general','correspondence','advice','attendance','billing')),
                    content      TEXT NOT NULL,
                    is_privileged INTEGER NOT NULL DEFAULT 1,
                    created_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """))

        # Seed if empty
        r = conn.execute(text("SELECT COUNT(*) FROM users")).fetchone()
        if r[0] == 0:
            _seed(conn)

    print(f"✓ Database initialised with {DATABASE_URL}")

def _seed(conn):
    """Insert initial data for Holingu Lawyers PNG."""
    from auth import get_password_hash
    kmaisan_pw_hash = get_password_hash("kilomike@2024")
    jonathan_pw_hash = get_password_hash("JH@2026")
    user_pw_hash = get_password_hash("kilomike@2024")

    users = [
        {"email":"user@holingu.com", "full_name":"Holingu User", "display_name":"User", "password_hash":user_pw_hash, "role":"admin", "admission_no":None, "tin":None, "phone":None},
        {"email":"kmaisan@dspng.tech", "full_name":"K. Maisan", "display_name":"K. Maisan", "password_hash":kmaisan_pw_hash, "role":"admin", "admission_no":None, "tin":None, "phone":None},
        {"email":"jonathan@holingu.com", "full_name":"Jonathan Holingu", "display_name":"Jonathan", "password_hash":jonathan_pw_hash, "role":"associate", "admission_no":"PNG/BAR/2026/0001", "tin":None, "phone":None}
    ]

    for u in users:
        conn.execute(text("""
            INSERT INTO users (email, full_name, display_name, password_hash, role, admission_no, tin, phone)
            VALUES (:email, :full_name, :display_name, :password_hash, :role, :admission_no, :tin, :phone)
        """), u)

    print("✓ Seed data inserted")
