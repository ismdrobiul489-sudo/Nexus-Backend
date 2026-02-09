import sqlite3
import os

db_path = "nexus_v2.db"

def migrate_and_fix():
    if not os.path.exists(db_path):
        print(f"Error: {db_path} not found!")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # 1. Add image_gen_config_id to flowconfig if missing
        print("Checking flowconfig table...")
        cursor.execute("PRAGMA table_info(flowconfig)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if "image_gen_config_id" not in columns:
            print("Adding image_gen_config_id column to flowconfig...")
            cursor.execute("ALTER TABLE flowconfig ADD COLUMN image_gen_config_id TEXT")
        else:
            print("image_gen_config_id already exists.")

        # 2. Enable background worker in appsettings
        print("Enabling background worker in appsettings...")
        cursor.execute("UPDATE appsettings SET enable_background_worker = 1")
        
        conn.commit()
        print("Database migration and fix completed successfully.")
    except Exception as e:
        print(f"Error during migration: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_and_fix()
