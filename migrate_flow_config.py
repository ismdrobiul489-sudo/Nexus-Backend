
import sqlite3
import os

db_path = "nexus_v2.db"

def migrate():
    if not os.path.exists(db_path):
        print(f"Error: Database {db_path} not found.")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    columns_to_add = [
        ("daily_limit", "INTEGER"),
        ("content_tone", "TEXT"),
        ("max_items_per_refresh", "INTEGER DEFAULT 5"),
        ("min_articles_required", "INTEGER DEFAULT 1"),
        ("posting_order", "TEXT DEFAULT 'NEWEST_FIRST'"),
        ("feed_added_timestamp", "REAL"),
        ("fallback_action", "TEXT DEFAULT 'MOVE_TO_REVIEW'")
    ]

    for col_name, col_type in columns_to_add:
        try:
            print(f"Adding column {col_name} to flowconfig...")
            cursor.execute(f"ALTER TABLE flowconfig ADD COLUMN {col_name} {col_type}")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                print(f"Column {col_name} already exists.")
            else:
                print(f"Error adding {col_name}: {e}")

    conn.commit()
    conn.close()
    print("Migration complete.")

if __name__ == "__main__":
    migrate()
