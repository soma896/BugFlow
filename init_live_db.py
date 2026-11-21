"""
BugFlow Production Database Initializer
Automatically creates tables and seeds canonical data when deploying to a live host (e.g. Render).
"""
import os
import sys
import json
from datetime import datetime, date

sys.path.insert(0, os.path.abspath("."))

from app.database import engine, SessionLocal
from app.models import (
    Base, User, Issue, Defect, Sprint, SprintIssue,
    AdminAction, AuditLog, Comment, Attachment, AuthSession
)
from sqlalchemy import text

def parse_val(v):
    if isinstance(v, str):
        # Try full ISO datetime first
        try:
            return datetime.fromisoformat(v)
        except Exception:
            pass
        # Try ISO date
        try:
            return date.fromisoformat(v)
        except Exception:
            pass
    return v

def init_db():
    print("[BugFlow] Connecting to database and ensuring schema tables exist...")
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    try:
        user_count = db.query(User).count()
        if user_count > 0:
            print(f"[BugFlow] Database already populated ({user_count} users found).")
            print("[BugFlow] Ensuring canonical persona accounts (Admin, Senior Dev, Developer, QA Tester)...")
            from app.main import ensure_canonical_persona_accounts
            ensure_canonical_persona_accounts(db)
            print("[BugFlow] Canonical accounts verified.")
            return

        seed_file = os.path.join(os.path.dirname(__file__), "seed_data.json")
        if not os.path.exists(seed_file):
            print("[BugFlow] seed_data.json not found, schema created without seed.")
            return

        print("[BugFlow] Seeding live database from seed_data.json...")
        with open(seed_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        model_map = [
            ("users", User),
            ("sprints", Sprint),
            ("issues", Issue),
            ("defects", Defect),
            ("sprint_issues", SprintIssue),
            ("admin_actions", AdminAction),
            ("audit_logs", AuditLog),
        ]

        for table_name, model in model_map:
            rows = data.get(table_name, [])
            for r in rows:
                parsed_row = {k: parse_val(v) for k, v in r.items()}
                obj = model(**parsed_row)
                db.add(obj)
            db.commit()
            print(f"  -> Inserted {len(rows)} records into '{table_name}'")

        # Sync PostgreSQL primary key sequences so future inserts don't collide
        try:
            for table_name, _ in model_map:
                db.execute(text(f"""
                    SELECT setval(
                        pg_get_serial_sequence('{table_name}', 'id'),
                        COALESCE((SELECT MAX(id) FROM {table_name}), 1)
                    );
                """))
            db.commit()
            print("[BugFlow] PostgreSQL primary key sequences synchronized.")
        except Exception as seq_err:
            print("[BugFlow] Sequence sync notice (non-fatal):", seq_err)

        print("[BugFlow] Database initialization and seeding completed successfully!")
    finally:
        db.close()

if __name__ == "__main__":
    init_db()
