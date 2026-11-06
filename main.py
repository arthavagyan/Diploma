"""Entry point: python main.py [path/to/database.db]"""

import sys

from src import database as db
from src.cli import run

if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else db.DEFAULT_DB_PATH)
