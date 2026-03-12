from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from database import get_db
import auth
from datetime import datetime, timedelta

router = APIRouter()
def row_to_dict(row): return dict(row._mapping) if row else None

@router.get("/dashboard")
def dashboard_analytics(db: Session = Depends(get_db), current_user: dict = Depends(auth.get_current_user)):
    """Full dashboard payload for the Intelligence Dashboard screen."""
    dialect = db.bind.dialect.name
    today = datetime.now().date()
    limit_30 = today + timedelta(days=30)
    limit_60 = today + timedelta(days=60)

    # Top stats
    stats = {}
    r = db.execute(text("SELECT COUNT(*) as c, COALESCE(SUM(value_pgk),0) as v FROM matters WHERE status='active'")).fetchone()
    stats["active_matters"] = r._mapping["c"]
    stats["total_value_pgk"] = r._mapping["v"]
    stats["risk_alerts"]   = db.execute(text("SELECT COUNT(*) FROM risk_flags WHERE status='open'")).scalar()
    stats["open_deadlines"]= db.execute(text("SELECT COUNT(*) FROM extracted_dates WHERE due_date >= :today"), {"today": today}).scalar()
    stats["critical_risks"]= db.execute(text("SELECT COUNT(*) FROM risk_flags WHERE severity IN ('critical','high') AND status='open'")).scalar()
    stats["deadlines_30d"] = db.execute(text("SELECT COUNT(*) FROM extracted_dates WHERE due_date BETWEEN :today AND :limit"), {"today": today, "limit": limit_30}).scalar()
    stats["docs_pending"]  = db.execute(text("SELECT COUNT(*) FROM documents WHERE analysis_status IN ('pending','processing')")).scalar()

    # Matter value by type
    by_type = [row_to_dict(r) for r in db.execute(text(
        "SELECT matter_type, COUNT(*) as count, COALESCE(SUM(value_pgk),0) as value_pgk FROM matters WHERE status='active' GROUP BY matter_type")).fetchall()]

    # Risk breakdown
    risk_breakdown = [row_to_dict(r) for r in db.execute(text(
        "SELECT severity, COUNT(*) as count FROM risk_flags WHERE status='open' GROUP BY severity ORDER BY CASE severity WHEN 'critical' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 ELSE 4 END")).fetchall()]

    # Upcoming critical deadlines (next 60 days)
    critical_deadlines = [row_to_dict(r) for r in db.execute(text("""
        SELECT ed.label, ed.due_date, ed.is_critical, ed.date_type, m.matter_ref
        FROM extracted_dates ed JOIN matters m ON m.id=ed.matter_id
        WHERE ed.due_date BETWEEN :today AND :limit
        ORDER BY ed.is_critical DESC, ed.due_date ASC LIMIT 8
    """), {"today": today, "limit": limit_60}).fetchall()]

    # Top open risks
    top_risks = [row_to_dict(r) for r in db.execute(text("""
        SELECT rf.severity, rf.flag_type, rf.clause_ref, rf.description, m.matter_ref
        FROM risk_flags rf JOIN matters m ON m.id=rf.matter_id
        WHERE rf.status='open'
        ORDER BY CASE rf.severity WHEN 'critical' THEN 1 WHEN 'high' THEN 2 ELSE 3 END
        LIMIT 6
    """)).fetchall()]

    # Deal flow (monthly totals — simulated from opened_date)
    if dialect == 'sqlite':
        df_sql = "SELECT strftime('%Y-%m', opened_date) as month, COUNT(*) as count, COALESCE(SUM(value_pgk),0) as value_pgk FROM matters GROUP BY month ORDER BY month DESC LIMIT 12"
    else:
        df_sql = "SELECT TO_CHAR(opened_date, 'YYYY-MM') as month, COUNT(*) as count, COALESCE(SUM(value_pgk),0) as value_pgk FROM matters GROUP BY TO_CHAR(opened_date, 'YYYY-MM') ORDER BY month DESC LIMIT 12"

    deal_flow = [row_to_dict(r) for r in db.execute(text(df_sql)).fetchall()]

    # Partners workload
    partners = [row_to_dict(r) for r in db.execute(text("""
        SELECT u.display_name, u.role,
               COUNT(m.id) as active_matters,
               COALESCE(SUM(m.value_pgk),0) as total_value
        FROM users u
        LEFT JOIN matters m ON m.lead_partner_id=u.id AND m.status='active'
        WHERE u.role IN ('senior_partner','partner','associate')
        GROUP BY u.id, u.display_name, u.role ORDER BY total_value DESC
    """)).fetchall()]

    return {
        "stats": stats,
        "by_type": by_type,
        "risk_breakdown": risk_breakdown,
        "critical_deadlines": critical_deadlines,
        "top_risks": top_risks,
        "deal_flow": list(reversed(deal_flow)),
        "partners_workload": partners,
    }

@router.get("/value")
def value_analytics(db: Session = Depends(get_db), current_user: dict = Depends(auth.get_current_user)):
    """Total matter value breakdown in PGK."""
    return {
        "by_status": [row_to_dict(r) for r in db.execute(text(
            "SELECT status, COUNT(*) as count, COALESCE(SUM(value_pgk),0) as value FROM matters GROUP BY status")).fetchall()],
        "by_type": [row_to_dict(r) for r in db.execute(text(
            "SELECT matter_type, COUNT(*) as count, COALESCE(SUM(value_pgk),0) as value FROM matters GROUP BY matter_type ORDER BY value DESC")).fetchall()],
        "by_partner": [row_to_dict(r) for r in db.execute(text("""
            SELECT u.display_name, COALESCE(SUM(m.value_pgk),0) as value
            FROM matters m JOIN users u ON u.id=m.lead_partner_id
            GROUP BY u.id, u.display_name ORDER BY value DESC
        """)).fetchall()],
    }
