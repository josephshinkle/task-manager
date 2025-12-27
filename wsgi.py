from pathlib import Path
from Project.app import app
from Project.db import init_db, migrate_db

if Path("/opt/render/project/data").exists():
    init_db()
    migrate_db()