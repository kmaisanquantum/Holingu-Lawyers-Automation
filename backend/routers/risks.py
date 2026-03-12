from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import text
from database import get_db
import auth

router = APIRouter()
def row_to_dict(row): return dict(row._mapping) if row else None

class RiskUpdate(BaseModel):
    status: Optional[str] = None
    recommendation: Optional[str] = None
    reviewed_by: Optional[int] = None

@router.get("")
def list_risks(
    severity: Optional[str] = None,
    status: Optional[str] = "open",
    matter_id: Optional[int] = None,
    db: Session = Depends(get_db)
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
    params = {}
    if severity:
        sql += " AND rf.severity=:severity"
        params["severity"] = severity
    if status:
        sql += " AND rf.status=:status"
        params["status"] = status
    if matter_id:
        sql += " AND rf.matter_id=:matter_id"
        params["matter_id"] = matter_id
    sql += " ORDER BY CASE rf.severity WHEN 'critical' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 ELSE 4 END"
    result = db.execute(text(sql), params)
    return [row_to_dict(r) for r in result.fetchall()]

@router.get("/summary")
def risk_summary(db: Session = Depends(get_db), current_user: dict = Depends(auth.get_current_user)):
    result = db.execute(text("SELECT severity, COUNT(*) as count FROM risk_flags WHERE status='open' GROUP BY severity"))
    by_sev = {r._mapping["severity"]: r._mapping["count"] for r in result.fetchall()}
    result2 = db.execute(text("SELECT flag_type, COUNT(*) as count FROM risk_flags WHERE status='open' GROUP BY flag_type ORDER BY count DESC"))
    by_type = [row_to_dict(r) for r in result2.fetchall()]
    return {"by_severity": by_sev, "by_type": by_type, "total_open": sum(by_sev.values())}

@router.get("/{risk_id}")
def get_risk(risk_id: int, db: Session = Depends(get_db)):
    result = db.execute(text("SELECT * FROM risk_flags WHERE id=:risk_id"), {"risk_id": risk_id})
    r = row_to_dict(result.fetchone())
    if not r: raise HTTPException(status_code=404, detail="Risk flag not found")
    return r

@router.patch("/{risk_id}")
def update_risk(risk_id: int, update: RiskUpdate, db: Session = Depends(get_db)):
    valid_statuses = ("open","reviewed","resolved","accepted")
    if update.status and update.status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Status must be one of {valid_statuses}")
    fields = {k: v for k, v in update.dict().items() if v is not None}
    if not fields: raise HTTPException(status_code=400, detail="Nothing to update")

    set_clause = ", ".join(f"{k}=:{k}" for k in fields) + ", updated_at=CURRENT_TIMESTAMP"
    if update.reviewed_by:
        set_clause += ", reviewed_at=CURRENT_TIMESTAMP"

    params = {**fields, "risk_id": risk_id}
    db.execute(text(f"UPDATE risk_flags SET {set_clause} WHERE id=:risk_id"), params)
    db.commit()
    return get_risk(risk_id, db)
