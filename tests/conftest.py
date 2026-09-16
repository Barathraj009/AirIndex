"""Test bootstrap: make the backend package importable and the app importable
when tests run from the repo root (or anywhere). Alembic/pytest both resolve
`app.*` when `backend/` is on sys.path."""

import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))
