from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import text
from database import get_db
import auth

router = APIRouter()

class MatterCreate(BaseModel):
    matter_ref: str
    title: str
    matter_type: str
    status: Optional[str] = "active"
    value_pgk: Optional[float] = None
    description: Optional[str] = None
    governing_law: Optional[str] = "Laws of Papua New Guinea"
    client_id: Optional[int] = None
    lead_partner_id: Optional[int] = None

class MatterUpdate(BaseModel):
    title: Optional[str] = None
    matter_type: Optional[str] = None
    status: Optional[str] = None
    value_pgk: Optional[float] = None
    description: Optional[str] = None
    governing_law: Optional[str] = None
    client_id: Optional[int] = None
    lead_partner_id: Optional[int] = None

def row_to_dict(row):
    if row is None: return None
    return dict(row._mapping)

@router.get("")
def list_matters(
    status: Optional[str] = None,
    matter_type: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(auth.get_current_user)
):
    sql = """
        SELECT m.*, c.name AS client_name, c.ipa_reg_no,
               u.display_name AS partner_name,
               (SELECT COUNT(*) FROM documents d WHERE d.matter_id=m.id) AS doc_count,
               (SELECT COUNT(*) FROM risk_flags r WHERE r.matter_id=m.id AND r.status='open') AS open_risks
        FROM matters m
        LEFT JOIN clients c ON c.id = m.client_id
        LEFT JOIN users   u ON u.id = m.lead_partner_id
        WHERE 1=1
    """
    params = {}
    if status:
        sql += " AND m.status=:status"
        params["status"] = status
    if matter_type:
        sql += " AND m.matter_type=:matter_type"
        params["matter_type"] = matter_type
    if search:
        sql += " AND (m.title LIKE :search OR m.matter_ref LIKE :search)"
        params["search"] = f"%{search}%"
    sql += " ORDER BY m.created_at DESC"
    result = db.execute(text(sql), params)
    return [row_to_dict(r) for r in result.fetchall()]

@router.get("/summary")
def matters_summary(db: Session = Depends(get_db)):
    result = db.execute(text("SELECT COUNT(*) as total, COALESCE(SUM(value_pgk),0) as total_value FROM matters WHERE status='active'"))
    row = row_to_dict(result.fetchone())

    by_type_result = db.execute(text("SELECT matter_type, COUNT(*) as count, COALESCE(SUM(value_pgk),0) as value FROM matters GROUP BY matter_type"))
    by_type = [row_to_dict(r) for r in by_type_result.fetchall()]

    by_status_result = db.execute(text("SELECT status, COUNT(*) as count FROM matters GROUP BY status"))
    by_status = [row_to_dict(r) for r in by_status_result.fetchall()]

    return {"active_count": row["total"], "total_value_pgk": row["total_value"], "by_type": by_type, "by_status": by_status}

@router.get("/{matter_ref}")
def get_matter(matter_ref: str, db: Session = Depends(get_db)):
    result = db.execute(text("""
        SELECT m.*, c.name AS client_name, c.ipa_reg_no, c.tin AS client_tin,
               u.display_name AS partner_name, u.admission_no
        FROM matters m
        LEFT JOIN clients c ON c.id=m.client_id
        LEFT JOIN users   u ON u.id=m.lead_partner_id
        WHERE m.matter_ref=:matter_ref
    """), {"matter_ref": matter_ref})
    matter = row_to_dict(result.fetchone())
    if not matter:
        raise HTTPException(status_code=404, detail=f"Matter {matter_ref} not found")

    # Attach related data
    docs_res = db.execute(text("SELECT * FROM documents WHERE matter_id=:mid ORDER BY created_at DESC"), {"mid": matter["id"]})
    matter["documents"] = [row_to_dict(r) for r in docs_res.fetchall()]

    risks_res = db.execute(text("SELECT * FROM risk_flags WHERE matter_id=:mid AND status='open' ORDER BY CASE severity WHEN 'critical' THEN 1 WHEN 'high' THEN 2 ELSE 3 END"), {"mid": matter["id"]})
    matter["risk_flags"] = [row_to_dict(r) for r in risks_res.fetchall()]

    dates_res = db.execute(text("SELECT * FROM extracted_dates WHERE matter_id=:mid ORDER BY due_date"), {"mid": matter["id"]})
    matter["deadlines"] = [row_to_dict(r) for r in dates_res.fetchall()]

    props_res = db.execute(text("SELECT * FROM property_references WHERE matter_id=:mid"), {"mid": matter["id"]})
    matter["property_refs"] = [row_to_dict(r) for r in props_res.fetchall()]

    notes_res = db.execute(text("SELECT mn.*, u.display_name AS author FROM matter_notes mn LEFT JOIN users u ON u.id=mn.author_id WHERE mn.matter_id=:mid ORDER BY mn.created_at DESC"), {"mid": matter["id"]})
    matter["notes"] = [row_to_dict(r) for r in notes_res.fetchall()]

    return matter

@router.post("", status_code=201)
def create_matter(matter: MatterCreate, db: Session = Depends(get_db)):
    try:
        db.execute(text("""
            INSERT INTO matters (matter_ref,title,matter_type,status,value_pgk,description,governing_law,client_id,lead_partner_id)
            VALUES (:matter_ref,:title,:matter_type,:status,:value_pgk,:description,:governing_law,:client_id,:lead_partner_id)
        """), matter.dict())
        db.commit()
        return get_matter(matter.matter_ref, db)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=409, detail=f"Error creating matter: {str(e)}")

@router.patch("/{matter_ref}")
def update_matter(matter_ref: str, update: MatterUpdate, db: Session = Depends(get_db)):
    result = db.execute(text("SELECT id FROM matters WHERE matter_ref=:ref"), {"ref": matter_ref})
    if not result.fetchone():
        raise HTTPException(status_code=404, detail="Matter not found")

    fields = {k: v for k, v in update.dict().items() if v is not None}
    if not fields:
        raise HTTPException(status_code=400, detail="No fields to update")

    set_clause = ", ".join(f"{k}=:{k}" for k in fields)
    params = {**fields, "matter_ref": matter_ref}

    db.execute(text(f"UPDATE matters SET {set_clause}, updated_at=CURRENT_TIMESTAMP WHERE matter_ref=:matter_ref"), params)
    db.commit()
    return get_matter(matter_ref, db)

@router.delete("/{matter_ref}", status_code=204)
def delete_matter(matter_ref: str, db: Session = Depends(get_db)):
    result = db.execute(text("DELETE FROM matters WHERE matter_ref=:ref"), {"ref": matter_ref})
    db.commit()
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Matter not found")
