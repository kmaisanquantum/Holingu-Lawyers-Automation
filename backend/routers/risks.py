from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from database import get_db
import sqlite3

router = APIRouter()
def row_to_dict(row): return dict(row) if row else None

class RiskUpdate(BaseModel):
    status: Optional[str] = None
    recommendation: Optional[str] = None
    reviewed_by: Optional[int] = None

@router.get("")
def list_risks(
    severity: Optional[str] = None,
    status: Optional[str] = "open",
    matter_id: Optional[int] = None,
    db: sqlite3.Connection = Depends(get_db)
):
    sql = """
        SELECT rf.*, m.matter_ref, m.title AS matter_title,
               d.original_name AS source_doc,
               u.display_name AS reviewer
        FROM risk_flags rf
        JOIN matters m ON m.id = rf.matter_id
        JOIN documents d ON d.id = rf.document_id
        LEFT JOIN users u ON u.id = rf.reviewed_by
        WHERE 1=1
    """
    params = []
    if severity:  sql += " AND rf.severity=?";   params.append(severity)
    if status:    sql += " AND rf.status=?";      params.append(status)
    if matter_id: sql += " AND rf.matter_id=?";  params.append(matter_id)
    sql += " ORDER BY CASE rf.severity WHEN 'critical' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 ELSE 4 END"
    return [row_to_dict(r) for r in db.execute(sql, params).fetchall()]

@router.get("/summary")
def risk_summary(db: sqlite3.Connection = Depends(get_db)):
    cur = db.execute("SELECT severity, COUNT(*) as count FROM risk_flags WHERE status='open' GROUP BY severity")
    by_sev = {r["severity"]: r["count"] for r in cur.fetchall()}
    cur2 = db.execute("SELECT flag_type, COUNT(*) as count FROM risk_flags WHERE status='open' GROUP BY flag_type ORDER BY count DESC")
    by_type = [row_to_dict(r) for r in cur2.fetchall()]
    return {"by_severity": by_sev, "by_type": by_type, "total_open": sum(by_sev.values())}

@router.get("/{risk_id}")
def get_risk(risk_id: int, db: sqlite3.Connection = Depends(get_db)):
    cur = db.execute("SELECT * FROM risk_flags WHERE id=?", (risk_id,))
    r = row_to_dict(cur.fetchone())
    if not r: raise HTTPException(status_code=404, detail="Risk flag not found")
    return r

@router.patch("/{risk_id}")
def update_risk(risk_id: int, update: RiskUpdate, db: sqlite3.Connection = Depends(get_db)):
    valid_statuses = ("open","reviewed","resolved","accepted")
    if update.status and update.status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Status must be one of {valid_statuses}")
    fields = {k: v for k, v in update.dict().items() if v is not None}
    if not fields: raise HTTPException(status_code=400, detail="Nothing to update")
    set_clause = ", ".join(f"{k}=?" for k in fields) + ", updated_at=datetime('now')"
    if update.reviewed_by:
        set_clause += ", reviewed_at=datetime('now')"
    db.execute(f"UPDATE risk_flags SET {set_clause} WHERE id=?", [*fields.values(), risk_id])
    db.commit()
    return get_risk(risk_id, db)
