import os
import sys

# Change directory to backend so that imports like 'from database import init_db' work
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.join(current_dir, "backend")
os.chdir(backend_dir)
sys.path.insert(0, backend_dir)

from main import app
