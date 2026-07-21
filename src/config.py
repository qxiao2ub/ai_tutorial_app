from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = BASE_DIR / "uploads"
DB_PATH = DATA_DIR / "app.db"
APP_NAME = "Anish AI Tutorial App"
AUTHOR_NAME = "Anish Khandalkar"
MENTOR_NAME = "Dr. Qingyang Xiao"
LECTURER_NAME = "Anish"
ADMIN_PASSCODE = os.getenv("ANISH_ADMIN_PASSCODE", "change-me")
DEMO_MODE = os.getenv("ANISH_APP_DEMO_MODE", "1") == "1"

DATA_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
