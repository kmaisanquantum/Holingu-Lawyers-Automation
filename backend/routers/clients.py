from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import text
from database import get_db
import auth

router = APIRouter()

def row_to_dict(row): return dict(row._mapping) if row else None

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
    db: Session = Depends(get_db),
    current_user: dict = Depends(auth.get_current_user)
):
    sql = "SELECT c.*, (SELECT COUNT(*) FROM matters m WHERE m.client_id=c.id) AS matter_count FROM clients c WHERE c.is_active=1"
    params = {}
    if client_type:
        sql += " AND c.client_type=:client_type"
        params["client_type"] = client_type
    if search:
        sql += " AND (c.name LIKE :search OR c.ipa_reg_no LIKE :search OR c.tin LIKE :search)"
        params["search"] = f"%{search}%"
    sql += " ORDER BY c.name"
    result = db.execute(text(sql), params)
    return [row_to_dict(r) for r in result.fetchall()]

@router.get("/{client_code}")
def get_client(client_code: str, db: Session = Depends(get_db)):
    result = db.execute(text("SELECT * FROM clients WHERE client_code=:client_code"), {"client_code": client_code})
    client = row_to_dict(result.fetchone())
    if not client: raise HTTPException(status_code=404, detail="Client not found")

    matters_result = db.execute(text("SELECT matter_ref,title,matter_type,status,value_pgk FROM matters WHERE client_id=:client_id ORDER BY created_at DESC"), {"client_id": client["id"]})
    client["matters"] = [row_to_dict(r) for r in matters_result.fetchall()]
    return client

@router.post("", status_code=201)
def create_client(client: ClientCreate, db: Session = Depends(get_db)):
    try:
        db.execute(text("""INSERT INTO clients (client_code,name,client_type,ipa_reg_no,tin,address,city,province,country,contact_name,contact_email,contact_phone,notes)
            VALUES (:client_code,:name,:client_type,:ipa_reg_no,:tin,:address,:city,:province,:country,:contact_name,:contact_email,:contact_phone,:notes)"""),
            client.dict())
        db.commit()
        return get_client(client.client_code, db)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=409, detail=f"Error creating client: {str(e)}")
