from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from database import get_db
import sqlite3

router = APIRouter()

def row_to_dict(row): return dict(row) if row else None

@router.get("")
def list_users(db: sqlite3.Connection = Depends(get_db)):
    cur = db.execute("SELECT id,email,full_name,display_name,role,admission_no,phone,is_active FROM users WHERE is_active=1 ORDER BY CASE role WHEN 'senior_partner' THEN 1 WHEN 'partner' THEN 2 WHEN 'associate' THEN 3 ELSE 4 END")
    return [row_to_dict(r) for r in cur.fetchall()]

@router.get("/{user_id}")
def get_user(user_id: int, db: sqlite3.Connection = Depends(get_db)):
    cur = db.execute("SELECT id,email,full_name,display_name,role,admission_no,phone FROM users WHERE id=?", (user_id,))
    u = row_to_dict(cur.fetchone())
    if not u: raise HTTPException(status_code=404, detail="User not found")
    u["matters"] = [row_to_dict(r) for r in db.execute(
        "SELECT matter_ref,title,status,value_pgk FROM matters WHERE lead_partner_id=? AND status='active'", (user_id,)).fetchall()]
    return u
