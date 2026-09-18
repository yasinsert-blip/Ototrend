"""Create a consistent SQLite backup without stopping the application."""

import os
import sqlite3
from datetime import UTC, datetime
from pathlib import Path


database_url = os.getenv("DATABASE_URL", "sqlite:////data/news.db")

if not database_url.startswith("sqlite:"):
    raise SystemExit("This backup helper only supports SQLite databases.")

database_path = Path(database_url.removeprefix("sqlite:///"))
backup_dir = Path(os.getenv("BACKUP_DIR", "/backups"))
backup_dir.mkdir(parents=True, exist_ok=True)

timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
backup_path = backup_dir / f"news-{timestamp}.db"

with sqlite3.connect(database_path, timeout=30) as source:
    with sqlite3.connect(backup_path) as destination:
        source.backup(destination)

print(f"SQLite backup created: {backup_path}")
