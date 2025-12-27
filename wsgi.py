from Project.app import app
from Project.db import init_db, migrate_db

init_db()
migrate_db()