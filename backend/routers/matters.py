from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List
from database import get_db
import sqlite3

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
    return dict(row)

@router.get("")
def list_matters(
    status: Optional[str] = None,
    matter_type: Optional[str] = None,
    search: Optional[str] = None,
    db: sqlite3.Connection = Depends(get_db)
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
    params = []
    if status:      sql += " AND m.status=?";                   params.append(status)
    if matter_type: sql += " AND m.matter_type=?";              params.append(matter_type)
    if search:      sql += " AND (m.title LIKE ? OR m.matter_ref LIKE ?)"; params += [f"%{search}%", f"%{search}%"]
    sql += " ORDER BY m.created_at DESC"
    cur = db.execute(sql, params)
    return [row_to_dict(r) for r in cur.fetchall()]

@router.get("/summary")
def matters_summary(db: sqlite3.Connection = Depends(get_db)):
    cur = db.execute("SELECT COUNT(*) as total, SUM(value_pgk) as total_value FROM matters WHERE status='active'")
    row = row_to_dict(cur.fetchone())
    cur2 = db.execute("SELECT matter_type, COUNT(*) as count, SUM(value_pgk) as value FROM matters GROUP BY matter_type")
    by_type = [row_to_dict(r) for r in cur2.fetchall()]
    cur3 = db.execute("SELECT status, COUNT(*) as count FROM matters GROUP BY status")
    by_status = [row_to_dict(r) for r in cur3.fetchall()]
    return {"active_count": row["total"], "total_value_pgk": row["total_value"], "by_type": by_type, "by_status": by_status}

@router.get("/{matter_ref}")
def get_matter(matter_ref: str, db: sqlite3.Connection = Depends(get_db)):
    cur = db.execute("""
        SELECT m.*, c.name AS client_name, c.ipa_reg_no, c.tin AS client_tin,
               u.display_name AS partner_name, u.admission_no
        FROM matters m
        LEFT JOIN clients c ON c.id=m.client_id
        LEFT JOIN users   u ON u.id=m.lead_partner_id
        WHERE m.matter_ref=?
    """, (matter_ref,))
    matter = row_to_dict(cur.fetchone())
    if not matter:
        raise HTTPException(status_code=404, detail=f"Matter {matter_ref} not found")

    # Attach related data
    matter["documents"] = [row_to_dict(r) for r in db.execute(
        "SELECT * FROM documents WHERE matter_id=? ORDER BY created_at DESC", (matter["id"],)).fetchall()]
    matter["risk_flags"] = [row_to_dict(r) for r in db.execute(
        "SELECT * FROM risk_flags WHERE matter_id=? AND status='open' ORDER BY CASE severity WHEN 'critical' THEN 1 WHEN 'high' THEN 2 ELSE 3 END", (matter["id"],)).fetchall()]
    matter["deadlines"] = [row_to_dict(r) for r in db.execute(
        "SELECT * FROM extracted_dates WHERE matter_id=? ORDER BY due_date", (matter["id"],)).fetchall()]
    matter["property_refs"] = [row_to_dict(r) for r in db.execute(
        "SELECT * FROM property_references WHERE matter_id=?", (matter["id"],)).fetchall()]
    matter["notes"] = [row_to_dict(r) for r in db.execute(
        "SELECT mn.*, u.display_name AS author FROM matter_notes mn LEFT JOIN users u ON u.id=mn.author_id WHERE mn.matter_id=? ORDER BY mn.created_at DESC", (matter["id"],)).fetchall()]
    return matter

@router.post("", status_code=201)
def create_matter(matter: MatterCreate, db: sqlite3.Connection = Depends(get_db)):
    try:
        cur = db.execute("""
            INSERT INTO matters (matter_ref,title,matter_type,status,value_pgk,description,governing_law,client_id,lead_partner_id)
            VALUES (?,?,?,?,?,?,?,?,?)
        """, (matter.matter_ref, matter.title, matter.matter_type, matter.status,
              matter.value_pgk, matter.description, matter.governing_law,
              matter.client_id, matter.lead_partner_id))
        db.commit()
        return get_matter(matter.matter_ref, db)
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail=f"Matter ref {matter.matter_ref} already exists")

@router.patch("/{matter_ref}")
def update_matter(matter_ref: str, update: MatterUpdate, db: sqlite3.Connection = Depends(get_db)):
    cur = db.execute("SELECT id FROM matters WHERE matter_ref=?", (matter_ref,))
    if not cur.fetchone():
        raise HTTPException(status_code=404, detail="Matter not found")
    fields = {k: v for k, v in update.dict().items() if v is not None}
    if not fields:
        raise HTTPException(status_code=400, detail="No fields to update")
    set_clause = ", ".join(f"{k}=?" for k in fields) + ", updated_at=datetime('now')"
    db.execute(f"UPDATE matters SET {set_clause} WHERE matter_ref=?", [*fields.values(), matter_ref])
    db.commit()
    return get_matter(matter_ref, db)

@router.delete("/{matter_ref}", status_code=204)
def delete_matter(matter_ref: str, db: sqlite3.Connection = Depends(get_db)):
    cur = db.execute("DELETE FROM matters WHERE matter_ref=?", (matter_ref,))
    db.commit()
    if cur.rowcount == 0:
        raise HTTPException(status_code=404, detail="Matter not found")
