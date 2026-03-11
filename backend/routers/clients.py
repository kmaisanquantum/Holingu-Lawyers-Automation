from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from database import get_db
import sqlite3

router = APIRouter()

def row_to_dict(row): return dict(row) if row else None

class ClientCreate(BaseModel):
    client_code: str
    name: str
    client_type: str
    ipa_reg_no: Optional[str] = None
    tin: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = "Port Moresby"
    province: Optional[str] = "NCD"
    country: Optional[str] = "Papua New Guinea"
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    notes: Optional[str] = None

@router.get("")
def list_clients(
    client_type: Optional[str] = None,
    search: Optional[str] = None,
    db: sqlite3.Connection = Depends(get_db)
):
    sql = "SELECT c.*, (SELECT COUNT(*) FROM matters m WHERE m.client_id=c.id) AS matter_count FROM clients c WHERE c.is_active=1"
    params = []
    if client_type: sql += " AND c.client_type=?"; params.append(client_type)
    if search:      sql += " AND (c.name LIKE ? OR c.ipa_reg_no LIKE ? OR c.tin LIKE ?)"; params += [f"%{search}%"]*3
    sql += " ORDER BY c.name"
    return [row_to_dict(r) for r in db.execute(sql, params).fetchall()]

@router.get("/{client_code}")
def get_client(client_code: str, db: sqlite3.Connection = Depends(get_db)):
    cur = db.execute("SELECT * FROM clients WHERE client_code=?", (client_code,))
    client = row_to_dict(cur.fetchone())
    if not client: raise HTTPException(status_code=404, detail="Client not found")
    client["matters"] = [row_to_dict(r) for r in db.execute(
        "SELECT matter_ref,title,matter_type,status,value_pgk FROM matters WHERE client_id=? ORDER BY created_at DESC", (client["id"],)).fetchall()]
    return client

@router.post("", status_code=201)
def create_client(client: ClientCreate, db: sqlite3.Connection = Depends(get_db)):
    try:
        db.execute("""INSERT INTO clients (client_code,name,client_type,ipa_reg_no,tin,address,city,province,country,contact_name,contact_email,contact_phone,notes)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (client.client_code, client.name, client.client_type, client.ipa_reg_no, client.tin,
             client.address, client.city, client.province, client.country,
             client.contact_name, client.contact_email, client.contact_phone, client.notes))
        db.commit()
        return get_client(client.client_code, db)
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="Client code already exists")
