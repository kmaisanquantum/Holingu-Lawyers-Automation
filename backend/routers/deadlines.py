from fastapi import APIRouter, HTTPException, Depends
from typing import Optional
from database import get_db
import sqlite3

router = APIRouter()
def row_to_dict(row): return dict(row) if row else None

@router.get("")
def list_deadlines(
    days_ahead: Optional[int] = 90,
    critical_only: Optional[bool] = False,
    matter_id: Optional[int] = None,
    db: sqlite3.Connection = Depends(get_db)
):
    sql = """
        SELECT ed.*, m.matter_ref, m.title AS matter_title,
               d.original_name AS source_doc
        FROM extracted_dates ed
        JOIN matters m ON m.id = ed.matter_id
        JOIN documents d ON d.id = ed.document_id
        WHERE ed.due_date >= date('now')
    """
    params = []
    if days_ahead:    sql += f" AND ed.due_date <= date('now', '+{int(days_ahead)} days')"
    if critical_only: sql += " AND ed.is_critical=1"
    if matter_id:     sql += " AND ed.matter_id=?"; params.append(matter_id)
    sql += " ORDER BY ed.due_date ASC"
    return [row_to_dict(r) for r in db.execute(sql, params).fetchall()]

@router.get("/overdue")
def overdue_deadlines(db: sqlite3.Connection = Depends(get_db)):
    cur = db.execute("""
        SELECT ed.*, m.matter_ref, m.title AS matter_title
        FROM extracted_dates ed
        JOIN matters m ON m.id = ed.matter_id
        WHERE ed.due_date < date('now')
        ORDER BY ed.due_date DESC
    """)
    return [row_to_dict(r) for r in cur.fetchall()]

@router.get("/alerts/pending")
def pending_alerts(db: sqlite3.Connection = Depends(get_db)):
    """Deadlines where alert should fire but hasn't been sent."""
    cur = db.execute("""
        SELECT ed.*, m.matter_ref, m.title AS matter_title, u.email AS partner_email
        FROM extracted_dates ed
        JOIN matters m ON m.id = ed.matter_id
        LEFT JOIN users u ON u.id = m.lead_partner_id
        WHERE ed.alert_sent = 0
          AND ed.due_date >= date('now')
          AND ed.due_date <= date('now', '+'||ed.alert_days_before||' days')
        ORDER BY ed.due_date ASC
    """)
    alerts = [row_to_dict(r) for r in cur.fetchall()]
    return {"count": len(alerts), "alerts": alerts}
