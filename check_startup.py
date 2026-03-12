import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.getcwd(), 'backend'))

try:
    import app
    print("✓ backend.app imported")
    import database
    print("✓ backend.database imported")
    import auth
    print("✓ backend.auth imported")
    from routers import matters, documents, clients, users, risks, deadlines, analytics, vault
    print("✓ all routers imported")

    # Try init_db (SQLite)
    database.init_db()
    print("✓ database.init_db() success")

except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
