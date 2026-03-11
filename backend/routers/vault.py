from fastapi import APIRouter, Depends, Query
from typing import Optional
from database import get_db
import sqlite3

router = APIRouter()
def row_to_dict(row): return dict(row) if row else None

@router.get("/search")
def vault_search(
    q: str = Query(..., description="Search query across all vault documents"),
    matter_type: Optional[str] = None,
    doc_type: Optional[str] = None,
    limit: int = 10,
    db: sqlite3.Connection = Depends(get_db)
):
    """
    Full-text keyword search across the document vault.
    (Production: replace with pgvector cosine similarity search)
    """
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
            d.original_name LIKE ? OR
            m.title LIKE ? OR
            m.matter_ref LIKE ? OR
            ep.party_name LIKE ? OR
            ef.label LIKE ?
        )
    """
    term = f"%{q}%"
    params = [term, term, term, term, term]
    if matter_type: sql += " AND m.matter_type=?"; params.append(matter_type)
    if doc_type:    sql += " AND d.doc_type=?";    params.append(doc_type)
    sql += f" GROUP BY d.id ORDER BY d.created_at DESC LIMIT {limit}"

    results = [row_to_dict(r) for r in db.execute(sql, params).fetchall()]
    return {"query": q, "count": len(results), "results": results}

@router.get("/stats")
def vault_stats(db: sqlite3.Connection = Depends(get_db)):
    """High-level vault statistics."""
    return {
        "total_documents":  db.execute("SELECT COUNT(*) FROM documents").fetchone()[0],
        "total_pages":      db.execute("SELECT COALESCE(SUM(page_count),0) FROM documents").fetchone()[0],
        "total_size_mb":    round((db.execute("SELECT COALESCE(SUM(file_size_kb),0) FROM documents").fetchone()[0] or 0) / 1024, 2),
        "analysed":         db.execute("SELECT COUNT(*) FROM documents WHERE analysis_status='analysed'").fetchone()[0],
        "pending":          db.execute("SELECT COUNT(*) FROM documents WHERE analysis_status IN ('pending','processing')").fetchone()[0],
        "parties_extracted":db.execute("SELECT COUNT(*) FROM extracted_parties").fetchone()[0],
        "financials_extracted": db.execute("SELECT COUNT(*) FROM extracted_financials").fetchone()[0],
        "risk_flags_total": db.execute("SELECT COUNT(*) FROM risk_flags").fetchone()[0],
        "indexed_embeddings":db.execute("SELECT COUNT(*) FROM document_embeddings WHERE embedding_status='indexed'").fetchone()[0],
    }

@router.get("/documents/recent")
def recent_documents(limit: int = 10, db: sqlite3.Connection = Depends(get_db)):
    cur = db.execute("""
        SELECT d.doc_ref, d.original_name, d.doc_type, d.analysis_status,
               d.page_count, d.created_at, m.matter_ref, m.title AS matter_title
        FROM documents d JOIN matters m ON m.id=d.matter_id
        ORDER BY d.created_at DESC LIMIT ?
    """, (limit,))
    return [row_to_dict(r) for r in cur.fetchall()]
