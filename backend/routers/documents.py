from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import text
from database import get_db
import hashlib, os, shutil
import auth

router = APIRouter()

UPLOAD_DIR = os.environ.get("UPLOAD_DIR", "./uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)  # Created at startup; /data/uploads on Render

def row_to_dict(row):
    return dict(row._mapping) if row else None

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
    db: Session = Depends(get_db),
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
    params = {}
    if matter_id:
        sql += " AND d.matter_id=:matter_id"
        params["matter_id"] = matter_id
    if analysis_status:
        sql += " AND d.analysis_status=:analysis_status"
        params["analysis_status"] = analysis_status
    if doc_type:
        sql += " AND d.doc_type=:doc_type"
        params["doc_type"] = doc_type
    sql += " ORDER BY d.created_at DESC"
    result = db.execute(text(sql), params)
    return [row_to_dict(r) for r in result.fetchall()]

@router.get("/pipeline")
def pipeline_status(db: Session = Depends(get_db)):
    """Document analysis pipeline overview."""
    result = db.execute(text("""
        SELECT d.analysis_status, COUNT(*) as count, SUM(d.page_count) as total_pages
        FROM documents d GROUP BY d.analysis_status
    """))
    return {"pipeline": [row_to_dict(r) for r in result.fetchall()]}

@router.get("/{doc_ref}")
def get_document(doc_ref: str, db: Session = Depends(get_db)):
    result = db.execute(text("SELECT * FROM documents WHERE doc_ref=:doc_ref"), {"doc_ref": doc_ref})
    doc = row_to_dict(result.fetchone())
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    doc["parties"]    = [row_to_dict(r) for r in db.execute(text("SELECT * FROM extracted_parties WHERE document_id=:doc_id"), {"doc_id": doc["id"]}).fetchall()]
    doc["financials"] = [row_to_dict(r) for r in db.execute(text("SELECT * FROM extracted_financials WHERE document_id=:doc_id"), {"doc_id": doc["id"]}).fetchall()]
    doc["dates"]      = [row_to_dict(r) for r in db.execute(text("SELECT * FROM extracted_dates WHERE document_id=:doc_id"), {"doc_id": doc["id"]}).fetchall()]
    doc["risks"]      = [row_to_dict(r) for r in db.execute(text("SELECT * FROM risk_flags WHERE document_id=:doc_id"), {"doc_id": doc["id"]}).fetchall()]
    return doc

@router.post("", status_code=201)
def create_document(doc: DocCreate, db: Session = Depends(get_db)):
    try:
        db.execute(text("""
            INSERT INTO documents (matter_id,doc_ref,filename,original_name,doc_type,version,page_count,file_size_kb,uploaded_by)
            VALUES (:matter_id,:doc_ref,:filename,:original_name,:doc_type,:version,:page_count,:file_size_kb,:uploaded_by)
        """), doc.dict())
        db.commit()
        return get_document(doc.doc_ref, db)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=409, detail=f"Error creating document: {str(e)}")

@router.post("/upload/{matter_ref}")
async def upload_document(matter_ref: str, file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Upload a PDF to the vault and queue for analysis."""
    result = db.execute(text("SELECT id FROM matters WHERE matter_ref=:matter_ref"), {"matter_ref": matter_ref})
    matter = row_to_dict(result.fetchone())
    if not matter:
        raise HTTPException(status_code=404, detail="Matter not found")

    content = await file.read()
    checksum = hashlib.sha256(content).hexdigest()
    safe_name = file.filename.replace(" ", "_").lower()
    file_path = os.path.join(UPLOAD_DIR, f"{matter_ref}_{safe_name}")

    with open(file_path, "wb") as f:
        f.write(content)

    # Auto-generate doc ref
    count_result = db.execute(text("SELECT COUNT(*) FROM documents"))
    count = count_result.scalar() + 1
    doc_ref = f"DOC-{2024}-{count:04d}"

    db.execute(text("""
        INSERT INTO documents (matter_id,doc_ref,filename,original_name,doc_type,file_size_kb,storage_path,checksum_sha256,analysis_status)
        VALUES (:matter_id,:doc_ref,:filename,:original_name,:doc_type,:file_size_kb,:storage_path,:checksum_sha256,'pending')
    """), {"matter_id": matter["id"], "doc_ref": doc_ref, "filename": safe_name,
          "original_name": file.filename, "doc_type": "other",
          "file_size_kb": len(content)//1024, "storage_path": file_path, "checksum_sha256": checksum})
    db.commit()
    return {"doc_ref": doc_ref, "filename": file.filename, "status": "pending", "size_kb": len(content)//1024}

@router.patch("/{doc_ref}/status")
def update_analysis_status(doc_ref: str, body: dict, db: Session = Depends(get_db)):
    new_status = body.get("analysis_status")
    if new_status not in ("pending","processing","analysed","failed","archived"):
        raise HTTPException(status_code=400, detail="Invalid status")
    db.execute(text("UPDATE documents SET analysis_status=:analysis_status, updated_at=CURRENT_TIMESTAMP WHERE doc_ref=:doc_ref"),
               {"analysis_status": new_status, "doc_ref": doc_ref})
    db.commit()
    return {"doc_ref": doc_ref, "analysis_status": new_status}
