from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import text
from database import get_db
import auth

router = APIRouter()

def row_to_dict(row): return dict(row._mapping) if row else None

class LoginRequest(BaseModel):
    email: str
    password: str

class UserCreate(BaseModel):
    email: str
    full_name: str
    display_name: str
    role: str
    password: Optional[str] = None
    admission_no: Optional[str] = None
    phone: Optional[str] = None

class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    display_name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[int] = None
    admission_no: Optional[str] = None
    phone: Optional[str] = None

@router.post("/login")
def login(req: LoginRequest, db: Session = Depends(get_db)):
    result = db.execute(text("SELECT id, email, password_hash, full_name, role FROM users WHERE email=:email AND is_active=1"), {"email": req.email})
    user = row_to_dict(result.fetchone())

    if not user or not auth.verify_password(req.password, user.get("password_hash")):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    # Create token
    access_token = auth.create_access_token(data={"sub": user["email"], "role": user["role"], "id": user["id"]})

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user["id"],
            "email": user["email"],
            "full_name": user["full_name"],
            "role": user["role"]
        }
    }

@router.get("")
def list_users(db: Session = Depends(get_db), current_user: dict = Depends(auth.get_current_user)):
    result = db.execute(text("SELECT id,email,full_name,display_name,role,admission_no,phone,is_active FROM users ORDER BY CASE role WHEN 'senior_partner' THEN 1 WHEN 'partner' THEN 2 WHEN 'associate' THEN 3 ELSE 4 END"))
    return [row_to_dict(r) for r in result.fetchall()]

@router.post("")
def create_user(user: UserCreate, db: Session = Depends(get_db), admin: dict = Depends(auth.require_admin)):
    try:
        password_hash = auth.get_password_hash(user.password or "Holingu2024")
        db.execute(text("""
            INSERT INTO users (email, full_name, display_name, role, password_hash, admission_no, phone, is_active)
            VALUES (:email, :full_name, :display_name, :role, :password_hash, :admission_no, :phone, 1)
        """), {**user.dict(exclude={"password"}), "password_hash": password_hash})
        db.commit()
        return {"message": "User created successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@router.patch("/{user_id}")
def update_user(user_id: int, update: UserUpdate, db: Session = Depends(get_db), admin: dict = Depends(auth.require_admin)):
    fields = {k: v for k, v in update.dict().items() if v is not None}
    if not fields: raise HTTPException(status_code=400, detail="Nothing to update")

    set_clause = ", ".join(f"{k}=:{k}" for k in fields)
    params = {**fields, "id": user_id}

    db.execute(text(f"UPDATE users SET {set_clause} WHERE id=:id"), params)
    db.commit()
    return {"message": "User updated"}

@router.delete("/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db), admin: dict = Depends(auth.require_admin)):
    # Deactivate instead of hard delete
    db.execute(text("UPDATE users SET is_active=0 WHERE id=:id"), {"id": user_id})
    db.commit()
    return {"message": "User deactivated"}

@router.get("/{user_id}")
def get_user(user_id: int, db: Session = Depends(get_db)):
    result = db.execute(text("SELECT id,email,full_name,display_name,role,admission_no,phone FROM users WHERE id=:id"), {"id": user_id})
    u = row_to_dict(result.fetchone())
    if not u: raise HTTPException(status_code=404, detail="User not found")

    matters_result = db.execute(text("SELECT matter_ref,title,status,value_pgk FROM matters WHERE lead_partner_id=:user_id AND status='active'"), {"user_id": user_id})
    u["matters"] = [row_to_dict(r) for r in matters_result.fetchall()]
    return u
