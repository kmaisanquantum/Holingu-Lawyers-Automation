from fastapi import APIRouter, Depends, Query
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import text
from database import get_db
import auth

router = APIRouter()
def row_to_dict(row): return dict(row._mapping) if row else None

@router.get("/search")
def vault_search(
    q: str = Query(..., description="Search query across all vault documents"),
    matter_type: Optional[str] = None,
    doc_type: Optional[str] = None,
    limit: int = 10,
    db: Session = Depends(get_db),
    current_user: dict = Depends(auth.get_current_user)
):
    """
    Full-text keyword search across the document vault.
    (Production: replace with pgvector cosine similarity search)
    """
    dialect = db.bind.dialect.name

    sql = """
        SELECT d.doc_ref, d.original_name, d.doc_type, d.page_count,
               d.analysis_status, m.matter_ref, m.title AS matter_title,
               m.matter_type,
               ep.party_name, ef.label AS financial_label
        FROM documents d
        JOIN matters m ON m.id = d.matter_id
        LEFT JOIN extracted_parties ep ON ep.document_id = d.id
        LEFT JOIN extracted_financials ef ON ef.document_id = d.id
        WHERE (
            d.original_name LIKE :q OR
            m.title LIKE :q OR
            m.matter_ref LIKE :q OR
            ep.party_name LIKE :q OR
            ef.label LIKE :q
        )
    """
    params = {"q": f"%{q}%"}
    if matter_type:
        sql += " AND m.matter_type=:matter_type"
        params["matter_type"] = matter_type
    if doc_type:
        sql += " AND d.doc_type=:doc_type"
        params["doc_type"] = doc_type

    # Standard SQL GROUP BY requires all non-aggregated columns in SELECT
    # PostgreSQL is stricter than SQLite here.
    if dialect != 'sqlite':
        sql += """ GROUP BY d.id, d.doc_ref, d.original_name, d.doc_type, d.page_count,
                           d.analysis_status, m.matter_ref, m.title, m.matter_type,
                           ep.party_name, ef.label """
    else:
        sql += " GROUP BY d.id "

    sql += f" ORDER BY d.created_at DESC LIMIT {int(limit)}"

    result = db.execute(text(sql), params)
    results = [row_to_dict(r) for r in result.fetchall()]
    return {"query": q, "count": len(results), "results": results}

@router.get("/stats")
def vault_stats(db: Session = Depends(get_db)):
    """High-level vault statistics."""
    return {
        "total_documents":  db.execute(text("SELECT COUNT(*) FROM documents")).scalar(),
        "total_pages":      db.execute(text("SELECT COALESCE(SUM(page_count),0) FROM documents")).scalar(),
        "total_size_mb":    round((db.execute(text("SELECT COALESCE(SUM(file_size_kb),0) FROM documents")).scalar() or 0) / 1024, 2),
        "analysed":         db.execute(text("SELECT COUNT(*) FROM documents WHERE analysis_status='analysed'")).scalar(),
        "pending":          db.execute(text("SELECT COUNT(*) FROM documents WHERE analysis_status IN ('pending','processing')")).scalar(),
        "parties_extracted":db.execute(text("SELECT COUNT(*) FROM extracted_parties")).scalar(),
        "financials_extracted": db.execute(text("SELECT COUNT(*) FROM extracted_financials")).scalar(),
        "risk_flags_total": db.execute(text("SELECT COUNT(*) FROM risk_flags")).scalar(),
        "indexed_embeddings":db.execute(text("SELECT COUNT(*) FROM document_embeddings WHERE embedding_status='indexed'")).scalar(),
    }

@router.get("/documents/recent")
def recent_documents(limit: int = 10, db: Session = Depends(get_db)):
    result = db.execute(text("""
        SELECT d.doc_ref, d.original_name, d.doc_type, d.analysis_status,
               d.page_count, d.created_at, m.matter_ref, m.title AS matter_title
        FROM documents d JOIN matters m ON m.id=d.matter_id
        ORDER BY d.created_at DESC LIMIT :limit
    """), {"limit": limit})
    return [row_to_dict(r) for r in result.fetchall()]
