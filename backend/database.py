"""
Database — SQLite via SQLAlchemy
Holingu Lawyers Vault, Port Moresby PNG
"""

import sqlite3
import os
from typing import Generator

# Use absolute paths relative to this file's location
_here = os.path.dirname(os.path.abspath(__file__))
# Default to /data/holingu_vault.db for persistent storage, fallback to local directory
_default_db_path = "/data/holingu_vault.db" if os.path.exists("/data") else os.path.normpath(os.path.join(_here, "database", "holingu_vault.db"))

DB_PATH = os.environ.get("DATABASE_PATH", _default_db_path)

def get_connection():
    db_dir = os.path.dirname(DB_PATH)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn

def get_db() -> Generator:
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    """Create all tables and seed data if database is fresh."""
    conn = get_connection()
    cur = conn.cursor()

    cur.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        email         TEXT NOT NULL UNIQUE,
        full_name     TEXT NOT NULL,
        display_name  TEXT NOT NULL,
        role          TEXT NOT NULL CHECK(role IN ('senior_partner','partner','associate','paralegal','admin')),
        admission_no  TEXT,
        tin           TEXT,
        phone         TEXT,
        is_active     INTEGER NOT NULL DEFAULT 1,
        created_at    TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
    );

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
    );

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
    );

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
    );

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
    );

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
    );

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
    );

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
    );

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
    );

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
    );

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
    );

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
    );

    CREATE TABLE IF NOT EXISTS matter_notes (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        matter_id    INTEGER NOT NULL REFERENCES matters(id) ON DELETE CASCADE,
        author_id    INTEGER REFERENCES users(id) ON DELETE SET NULL,
        note_type    TEXT DEFAULT 'general' CHECK(note_type IN ('general','correspondence','advice','attendance','billing')),
        content      TEXT NOT NULL,
        is_privileged INTEGER NOT NULL DEFAULT 1,
        created_at   TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at   TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE INDEX IF NOT EXISTS idx_matters_ref      ON matters(matter_ref);
    CREATE INDEX IF NOT EXISTS idx_matters_status   ON matters(status);
    CREATE INDEX IF NOT EXISTS idx_documents_matter ON documents(matter_id);
    CREATE INDEX IF NOT EXISTS idx_dates_due        ON extracted_dates(due_date);
    CREATE INDEX IF NOT EXISTS idx_dates_critical   ON extracted_dates(is_critical);
    CREATE INDEX IF NOT EXISTS idx_risks_severity   ON risk_flags(severity);
    CREATE INDEX IF NOT EXISTS idx_risks_status     ON risk_flags(status);
    CREATE INDEX IF NOT EXISTS idx_audit_entity     ON audit_log(entity_type, entity_id);
    """)

    # Seed if empty
    cur.execute("SELECT COUNT(*) FROM users")
    if cur.fetchone()[0] == 0:
        _seed(conn, cur)

    conn.commit()
    conn.close()
    print(f"✓ Database initialised at {DB_PATH}")


def _seed(conn, cur):
    """Insert initial data for Holingu Lawyers PNG."""
    users = [
        ("a.holingu@holingu.pg","Advocate A. Holingu","A. Holingu","senior_partner","PNG/BAR/2001/0045","501-847-001","+675 7201 4567"),
        ("p.naime@holingu.pg","Philip Naime","P. Naime","partner","PNG/BAR/2008/0112","501-847-002","+675 7301 2345"),
        ("r.kaupa@holingu.pg","Rachel Kaupa","R. Kaupa","partner","PNG/BAR/2010/0178","501-847-003","+675 7401 3456"),
        ("t.mondo@holingu.pg","Thomas Mondo","T. Mondo","associate","PNG/BAR/2018/0344","501-847-004","+675 7501 4567"),
        ("admin@holingu.pg","System Administrator","Admin","admin",None,None,"+675 7601 5678"),
    ]
    cur.executemany("INSERT OR IGNORE INTO users (email,full_name,display_name,role,admission_no,tin,phone) VALUES (?,?,?,?,?,?,?)", users)

    clients = [
        ("CLT-001","Ela Beach Holdings Ltd.","company","1-84721","203-001-001","Level 5, Mogoru Moto, Champion Parade","Port Moresby","NCD"),
        ("CLT-002","Pacific Capital Group Ltd.","company","1-92034","203-002-002","Harbour City Office Tower, NCD","Port Moresby","NCD"),
        ("CLT-003","Waigani Commercial Properties Ltd.","company","1-77341","203-003-003","Section 50, Allotment 12, Waigani","Port Moresby","NCD"),
        ("CLT-004","Kumul Petroleum Holdings Ltd.","government","GOV-0001","203-004-004","P.O. Box 1006, Port Moresby","Port Moresby","NCD"),
        ("CLT-005","Highlands Resources Ltd.","company","1-65432","203-005-005","P.O. Box 4521, Lae","Lae","Morobe"),
        ("CLT-006","National Capital District Commission","government","GOV-0002","203-006-006","P.O. Box 7270, Boroko, NCD","Port Moresby","NCD"),
        ("CLT-007","PNG Ports Corporation Ltd.","government","GOV-0003","203-007-007","P.O. Box 671, Port Moresby","Port Moresby","NCD"),
    ]
    cur.executemany("INSERT OR IGNORE INTO clients (client_code,name,client_type,ipa_reg_no,tin,address,city,province) VALUES (?,?,?,?,?,?,?,?)", clients)

    def uid(email): cur.execute("SELECT id FROM users WHERE email=?", (email,)); return cur.fetchone()[0]
    def cid(code):  cur.execute("SELECT id FROM clients WHERE client_code=?", (code,)); return cur.fetchone()[0]
    h,n,k = uid("a.holingu@holingu.pg"), uid("p.naime@holingu.pg"), uid("r.kaupa@holingu.pg")

    matters = [
        ("HLG-2024-001","Ela Beach Tower — Land Title Transfer","deed","active",8500000,cid("CLT-001"),h,"Laws of Papua New Guinea, Land Act Chapter 185"),
        ("HLG-2024-002","Pacific Capital Group — M&A Acquisition","deal","active",42000000,cid("CLT-002"),n,"Laws of Papua New Guinea, Companies Act 1997"),
        ("HLG-2024-003","Waigani Commercial Centre — Commercial Lease","contract","active",1200000,cid("CLT-003"),k,"Laws of Papua New Guinea"),
        ("HLG-2024-004","Kumul Petroleum — Confidentiality Deed","deal","on_hold",6700000,cid("CLT-004"),h,"Laws of Papua New Guinea"),
        ("HLG-2024-005","Highlands Resources Ltd — Mining Lease Deed","mining","active",15400000,cid("CLT-005"),n,"Laws of Papua New Guinea, Mining Act 1992"),
        ("HLG-2024-006","Port Moresby NCD — Tenancy Framework","contract","closed",820000,cid("CLT-006"),k,"Laws of Papua New Guinea"),
        ("HLG-2024-007","PNG Ports Corporation — Logistics Services","deal","active",9500000,cid("CLT-007"),h,"Laws of Papua New Guinea"),
    ]
    cur.executemany("INSERT OR IGNORE INTO matters (matter_ref,title,matter_type,status,value_pgk,client_id,lead_partner_id,governing_law) VALUES (?,?,?,?,?,?,?,?)", matters)

    def mid(ref): cur.execute("SELECT id FROM matters WHERE matter_ref=?", (ref,)); return cur.fetchone()[0]
    admin_id = uid("admin@holingu.pg")
    m1,m2,m3,m4,m5,m7 = mid("HLG-2024-001"),mid("HLG-2024-002"),mid("HLG-2024-003"),mid("HLG-2024-004"),mid("HLG-2024-005"),mid("HLG-2024-007")

    docs = [
        (m1,"DOC-2024-0001","ela_beach_deed_v3.pdf","Ela Beach Tower — State Lease Vol.34 Fol.88.pdf","deed",3,42,1840,"analysed",1,"2024-02-10",admin_id),
        (m2,"DOC-2024-0002","pacific_capital_spa.pdf","Pacific Capital — Share Purchase Agreement.pdf","agreement",1,118,5210,"analysed",0,None,admin_id),
        (m3,"DOC-2024-0003","waigani_lease.pdf","Waigani Commercial Centre — Lease Agreement.pdf","lease",2,38,1540,"analysed",1,"2024-01-15",admin_id),
        (m4,"DOC-2024-0004","kumul_confidentiality.pdf","Kumul Petroleum — Confidentiality Deed.pdf","deed",1,14,620,"processing",0,None,admin_id),
        (m5,"DOC-2024-0005","highlands_ml157.pdf","Highlands Resources — Mining Lease ML 157.pdf","deed",1,67,2980,"analysed",1,"2024-03-01",admin_id),
        (m7,"DOC-2024-0006","png_ports_services.pdf","PNG Ports — Logistics Services Agreement.pdf","agreement",1,89,3870,"pending",0,None,admin_id),
        (m2,"DOC-2024-0007","pacific_due_diligence.pdf","Pacific Capital — Due Diligence Report.pdf","other",1,204,8920,"analysed",0,None,n),
    ]
    cur.executemany("INSERT OR IGNORE INTO documents (matter_id,doc_ref,filename,original_name,doc_type,version,page_count,file_size_kb,analysis_status,is_executed,execution_date,uploaded_by) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", docs)

    def did(ref): cur.execute("SELECT id FROM documents WHERE doc_ref=?", (ref,)); return cur.fetchone()[0]
    d1,d2,d3,d4,d5,d7 = did("DOC-2024-0001"),did("DOC-2024-0002"),did("DOC-2024-0003"),did("DOC-2024-0004"),did("DOC-2024-0005"),did("DOC-2024-0007")

    risks = [
        (d1,m1,"unlimited_liability","critical","Cl. 18.4","Unlimited warranty exposure on title — no cap on vendor liability under PNG Land Act","Negotiate warranty cap at 100% of consideration","open",0.94),
        (d2,m2,"unusual_indemnity","high","Cl. 9.2","Broad indemnity clause — indemnifier exposed to consequential losses without monetary limit","Cap indemnity at purchase price; exclude consequential loss","open",0.91),
        (d5,m5,"one_sided_termination","high","Cl. 14.1","State has unilateral termination right without compensation","Seek amendment per Mining Act 1992 s.112","open",0.89),
        (d4,m4,"dispute_resolution_gap","medium","Cl. 6.8","Dispute resolution clause does not specify PNG arbitration seat","Insert PNGDRC arbitration clause seated in Port Moresby","open",0.87),
        (d3,m3,"missing_force_majeure","medium","Cl. 22","No force majeure provision — tenant exposed during natural disasters","Insert standard PNG force majeure clause","open",0.85),
        (d2,m2,"warranty_breach_risk","medium","Cl. 11.3","Warranty disclosure schedule incomplete — IPA filings not disclosed","Conduct full IPA company search before completion","open",0.83),
        (d1,m1,"customary_land_issue","high","Cl. 3.1","State Lease boundaries abut customary land — no survey evidence","Commission PNG Lands Department survey","open",0.88),
    ]
    cur.executemany("INSERT OR IGNORE INTO risk_flags (document_id,matter_id,flag_type,severity,clause_ref,description,recommendation,status,ai_confidence) VALUES (?,?,?,?,?,?,?,?,?)", risks)

    dates = [
        (d1,m1,"completion","Settlement / Completion Date","2024-04-14","Cl. 8.1",21,0,1,"Critical path — notify IRC 30 days prior"),
        (d1,m1,"filing","IRC Stamp Duty Filing Deadline","2024-04-28","Cl. 9.2",14,0,1,"Penalty applies after 30 days"),
        (d2,m2,"sunset","Longstop Completion Date","2024-04-30","Cl. 5.4",30,0,1,"Buyer may rescind after this date"),
        (d2,m2,"milestone","Completion Accounts Delivery","2024-04-07","Cl. 6.1",14,0,0,"Accounts to be prepared by Vendor"),
        (d4,m4,"option","Option Exercise Window","2024-05-08","Cl. 4.3",14,0,0,"Kumul to notify in writing"),
        (d5,m5,"milestone","Royalty Payment Milestone #2","2024-05-22","Cl. 12.4",14,0,0,"Annual royalty — Q2 instalment"),
        (d5,m5,"expiry","Mining Lease ML 157 Expiry","2044-08-15","Cl. 2.1",365,0,0,"Renewal application 12 months prior"),
        (d7,m7,"expiry","Confidentiality Deed Expiry","2024-06-15","Cl. 11.1",14,0,0,"Auto-renewal unless written notice"),
    ]
    cur.executemany("INSERT OR IGNORE INTO extracted_dates (document_id,matter_id,date_type,label,due_date,clause_ref,alert_days_before,alert_sent,is_critical,notes,ai_confidence) VALUES (?,?,?,?,?,?,?,?,?,?,0.93)", dates)

    financials = [
        (d1,"consideration","Purchase Consideration",8500000,"PGK",None,"Full amount on settlement",0.98,1),
        (d1,"stamp_duty","Stamp Duty (IRC)",425000,"PGK",None,"5% of consideration — IRC assessed",0.95,1),
        (d2,"consideration","Share Purchase Price",42000000,"PGK",None,"Subject to completion accounts",0.97,0),
        (d2,"warranty_cap","Warranty Liability Cap",8400000,"PGK",None,"20% of purchase price",0.91,0),
        (d3,"rent","Annual Rent",1200000,"PGK",None,"Payable quarterly in advance",0.99,1),
        (d3,"bond","Security Deposit",300000,"PGK",None,"3 months rent — held in trust",0.98,1),
        (d5,"royalty","Annual Royalty Payment",None,"PGK",2.0,"2% of gross revenue, Mining Act s.97",0.97,1),
        (d5,"security_bond","Environmental Security Bond",1540000,"PGK",None,"PNG Dept of Environment",0.95,1),
    ]
    cur.executemany("INSERT OR IGNORE INTO extracted_financials (document_id,financial_type,label,amount,currency,rate_pct,detail,ai_confidence,is_verified) VALUES (?,?,?,?,?,?,?,?,?)", financials)

    parties = [
        (d1,"Lessor","Independent State of Papua New Guinea","government","GOV-PNG","—","Waigani, NCD",0.99,1),
        (d1,"Lessee","Ela Beach Holdings Ltd.","company","1-84721","203-001-001","Champion Parade, NCD",0.97,1),
        (d2,"Vendor","Pacific Capital Group Ltd.","company","1-92034","203-002-002","Harbour City, NCD",0.95,1),
        (d2,"Purchaser","PNG Pacific Investments Pty Ltd.","company","1-10234","203-009-009","Level 2, BSP Tower",0.92,0),
        (d3,"Lessor","Waigani Commercial Properties Ltd.","company","1-77341","203-003-003","Section 50 Waigani",0.98,1),
        (d3,"Lessee","PNG Retail Group Ltd.","company","1-55678","203-011-011","Gordons, NCD",0.96,1),
        (d5,"Lessee","Highlands Resources Ltd.","company","1-65432","203-005-005","P.O. Box 4521, Lae",0.99,1),
        (d5,"Lessor","Independent State of Papua New Guinea","government","GOV-PNG","—","Waigani, NCD",0.99,1),
    ]
    cur.executemany("INSERT OR IGNORE INTO extracted_parties (document_id,party_role,party_name,party_type,ipa_reg_no,tin,address,ai_confidence,is_verified) VALUES (?,?,?,?,?,?,?,?,?)", parties)

    props = [
        (m1,"state_lease","34","88","SL 2019/001","Ela Beach Tower Site","Champion Parade, Ela Beach","NCD",0.42,"2049-12-31"),
        (m3,"state_lease","71","201","SL 2015/044","Waigani Commercial Allotment","Section 50 Lot 12, Waigani","NCD",1.20,"2055-06-30"),
        (m5,"mining_lease",None,None,"ML 157","Highlands Gold Concession","Kainantu District","Eastern Highlands",8450.0,"2044-08-15"),
    ]
    cur.executemany("INSERT OR IGNORE INTO property_references (matter_id,ref_type,volume,folio,lease_no,land_name,location,province,area_hectares,lease_expiry) VALUES (?,?,?,?,?,?,?,?,?,?)", props)

    embeddings = [
        (d1,"indexed",8,"2024-03-01"),
        (d2,"indexed",22,"2024-03-02"),
        (d3,"indexed",7,"2024-02-20"),
        (d4,"processing",None,None),
        (d5,"indexed",14,"2024-03-05"),
    ]
    cur.executemany("INSERT OR IGNORE INTO document_embeddings (document_id,embedding_status,chunk_count,indexed_at) VALUES (?,?,?,?)", embeddings)

    conn.commit()
    print("✓ Seed data inserted")
