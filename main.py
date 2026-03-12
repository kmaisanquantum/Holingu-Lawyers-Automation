import os
import sys

# Get absolute path to the backend directory
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.join(current_dir, "backend")

# Insert backend directory to sys.path so that 'from app import app' works
# and internal imports within the backend package also work.
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# Import the FastAPI app from backend/app.py
from app import app
