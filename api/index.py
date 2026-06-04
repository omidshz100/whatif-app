import sys
import os

# Add the backend directory to the Python path so its modules are importable
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'backend'))

from main import app  # noqa: F401  — Vercel picks up the ASGI `app` export
