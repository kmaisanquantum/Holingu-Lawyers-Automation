from fastapi import APIRouter, HTTPException, Depends
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import text
from database import get_db
import auth
from datetime import datetime, timedelta

router = APIRouter()
def row_to_dict(row): return dict(row._mapping) if row else None

@router.get("")
def list_deadlines(
    days_ahead: Optional[int] = 90,
    critical_only: Optional[bool] = False,
    matter_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(auth.get_current_user)
):
    sql = """
        SELECT ed.*, m.matter_ref, m.title AS matter_title,
               d.original_name AS source_doc
        FROM extracted_dates ed
        JOIN matters m ON m.id = ed.matter_id
        JOIN documents d ON d.id = ed.document_id
        WHERE ed.due_date >= :today
    """
    params = {"today": datetime.now().date()}
    if days_ahead:
        sql += " AND ed.due_date <= :limit_date"
        params["limit_date"] = datetime.now().date() + timedelta(days=days_ahead)
    if critical_only:
        sql += " AND ed.is_critical=1"
    if matter_id:
        sql += " AND ed.matter_id=:matter_id"
        params["matter_id"] = matter_id
    sql += " ORDER BY ed.due_date ASC"
    result = db.execute(text(sql), params)
    return [row_to_dict(r) for r in result.fetchall()]

@router.get("/overdue")
def overdue_deadlines(db: Session = Depends(get_db)):
    result = db.execute(text("""
        SELECT ed.*, m.matter_ref, m.title AS matter_title
        FROM extracted_dates ed
        JOIN matters m ON m.id = ed.matter_id
        WHERE ed.due_date < :today
        ORDER BY ed.due_date DESC
    """), {"today": datetime.now().date()})
    return [row_to_dict(r) for r in result.fetchall()]

@router.get("/alerts/pending")
def pending_alerts(db: Session = Depends(get_db)):
    """Deadlines where alert should fire but hasn't been sent."""
    # This one is tricky due to interval calculation in SQL.
    # For now, we'll fetch all upcoming and filter in Python if needed,
    # but let's try a common approach if possible.
    # Actually, alert_days_before is a column.

    # To keep it simple and portable, we'll fetch upcoming and check the alert condition.
    result = db.execute(text("""
        SELECT ed.*, m.matter_ref, m.title AS matter_title, u.email AS partner_email
        FROM extracted_dates ed
        JOIN matters m ON m.id = ed.matter_id
        LEFT JOIN users u ON u.id = m.lead_partner_id
        WHERE ed.alert_sent = 0
          AND ed.due_date >= :today
    """), {"today": datetime.now().date()})

    all_upcoming = result.fetchall()
    alerts = []
    today = datetime.now().date()
    for row in all_upcoming:
        d = row_to_dict(row)
        due_date = datetime.strptime(d["due_date"][:10], "%Y-%m-%d").date() if isinstance(d["due_date"], str) else d["due_date"]
        if due_date <= today + timedelta(days=d["alert_days_before"]):
            alerts.append(d)

    return {"count": len(alerts), "alerts": alerts}
