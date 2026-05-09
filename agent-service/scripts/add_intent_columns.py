"""Add pending_intent, missing_slots, context_data columns to conversations table."""
import sqlite3
import sys
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "database.db"

COLUMNS = [
    ("pending_intent", "VARCHAR(64)"),
    ("missing_slots", "TEXT"),
    ("context_data", "TEXT"),
]


def main():
    if not DB_PATH.exists():
        print(f"Database not found at {DB_PATH}. Will be created on next startup.")
        return

    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(conversations)")
    existing = {row[1] for row in cursor.fetchall()}

    for col_name, col_type in COLUMNS:
        if col_name not in existing:
            cursor.execute(f"ALTER TABLE conversations ADD COLUMN {col_name} {col_type}")
            print(f"Added column: {col_name}")
        else:
            print(f"Column already exists: {col_name}")

    conn.commit()
    conn.close()
    print("Done.")


if __name__ == "__main__":
    main()
