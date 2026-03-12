from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from pydantic import BaseModel
from typing import Optional
from database import get_db
import sqlite3, hashlib, os, shutil
import auth

router = APIRouter()

UPLOAD_DIR = os.environ.get("UPLOAD_DIR", "./uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)  # Created at startup; /data/uploads on Render

def row_to_dict(row):
    return dict(row) if row else None

class DocCreate(BaseModel):
    matter_id: int
    doc_ref: str
    filename: str
    original_name: str
    doc_type: str
    version: Optional[int] = 1
    page_count: Optional[int] = None
    file_size_kb: Optional[int] = None
    uploaded_by: Optional[int] = None

@router.get("")
def list_documents(
    matter_id: Optional[int] = None,
    analysis_status: Optional[str] = None,
    doc_type: Optional[str] = None,
    db: sqlite3.Connection = Depends(get_db),
    current_user: dict = Depends(auth.get_current_user)
):
    sql = """
        SELECT d.*, m.matter_ref, m.title AS matter_title,
               u.display_name AS uploader,
               de.embedding_status, de.indexed_at
        FROM documents d
        LEFT JOIN matters m ON m.id = d.matter_id
        LEFT JOIN users   u ON u.id = d.uploaded_by
        LEFT JOIN document_embeddings de ON de.document_id = d.id
        WHERE 1=1
    """
    params = []
    if matter_id:       sql += " AND d.matter_id=?";        params.append(matter_id)
    if analysis_status: sql += " AND d.analysis_status=?";  params.append(analysis_status)
    if doc_type:        sql += " AND d.doc_type=?";         params.append(doc_type)
    sql += " ORDER BY d.created_at DESC"
    return [row_to_dict(r) for r in db.execute(sql, params).fetchall()]

@router.get("/pipeline")
def pipeline_status(db: sqlite3.Connection = Depends(get_db)):
    """Document analysis pipeline overview."""
    cur = db.execute("""
        SELECT d.analysis_status, COUNT(*) as count, SUM(d.page_count) as total_pages
        FROM documents d GROUP BY d.analysis_status
    """)
    return {"pipeline": [row_to_dict(r) for r in cur.fetchall()]}

@router.get("/{doc_ref}")
def get_document(doc_ref: str, db: sqlite3.Connection = Depends(get_db)):
    cur = db.execute("SELECT * FROM documents WHERE doc_ref=?", (doc_ref,))
    doc = row_to_dict(cur.fetchone())
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    doc["parties"]    = [row_to_dict(r) for r in db.execute("SELECT * FROM extracted_parties WHERE document_id=?", (doc["id"],)).fetchall()]
    doc["financials"] = [row_to_dict(r) for r in db.execute("SELECT * FROM extracted_financials WHERE document_id=?", (doc["id"],)).fetchall()]
    doc["dates"]      = [row_to_dict(r) for r in db.execute("SELECT * FROM extracted_dates WHERE document_id=?", (doc["id"],)).fetchall()]
    doc["risks"]      = [row_to_dict(r) for r in db.execute("SELECT * FROM risk_flags WHERE document_id=?", (doc["id"],)).fetchall()]
    return doc

@router.post("", status_code=201)
def create_document(doc: DocCreate, db: sqlite3.Connection = Depends(get_db)):
    try:
        db.execute("""
            INSERT INTO documents (matter_id,doc_ref,filename,original_name,doc_type,version,page_count,file_size_kb,uploaded_by)
            VALUES (?,?,?,?,?,?,?,?,?)
        """, (doc.matter_id, doc.doc_ref, doc.filename, doc.original_name,
              doc.doc_type, doc.version, doc.page_count, doc.file_size_kb, doc.uploaded_by))
        db.commit()
        return get_document(doc.doc_ref, db)
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="Document ref already exists")

@router.post("/upload/{matter_ref}")
async def upload_document(matter_ref: str, file: UploadFile = File(...), db: sqlite3.Connection = Depends(get_db)):
    """Upload a PDF to the vault and queue for analysis."""
    cur = db.execute("SELECT id FROM matters WHERE matter_ref=?", (matter_ref,))
    matter = cur.fetchone()
    if not matter:
        raise HTTPException(status_code=404, detail="Matter not found")

    content = await file.read()
    checksum = hashlib.sha256(content).hexdigest()
    safe_name = file.filename.replace(" ", "_").lower()
    file_path = os.path.join(UPLOAD_DIR, f"{matter_ref}_{safe_name}")

    with open(file_path, "wb") as f:
        f.write(content)

    # Auto-generate doc ref
    cur = db.execute("SELECT COUNT(*) FROM documents")
    count = cur.fetchone()[0] + 1
    doc_ref = f"DOC-{2024}-{count:04d}"

    db.execute("""
        INSERT INTO documents (matter_id,doc_ref,filename,original_name,doc_type,file_size_kb,storage_path,checksum_sha256,analysis_status)
        VALUES (?,?,?,?,?,?,?,?,'pending')
    """, (matter["id"], doc_ref, safe_name, file.filename, "other",
          len(content)//1024, file_path, checksum))
    db.commit()
    return {"doc_ref": doc_ref, "filename": file.filename, "status": "pending", "size_kb": len(content)//1024}

@router.patch("/{doc_ref}/status")
def update_analysis_status(doc_ref: str, body: dict, db: sqlite3.Connection = Depends(get_db)):
    new_status = body.get("analysis_status")
    if new_status not in ("pending","processing","analysed","failed","archived"):
        raise HTTPException(status_code=400, detail="Invalid status")
    db.execute("UPDATE documents SET analysis_status=?, updated_at=datetime('now') WHERE doc_ref=?", (new_status, doc_ref))
    db.commit()
    return {"doc_ref": doc_ref, "analysis_status": new_status}
