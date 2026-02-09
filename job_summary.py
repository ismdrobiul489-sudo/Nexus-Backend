import sqlite3
import os

db_path = "e:/coding/Antigravity/fba---facebook-automation-assistant/backend/nexus_v2.db"

def count_jobs():
    if not os.path.exists(db_path):
        print("Database missing.")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT type, status, COUNT(*) FROM job GROUP BY type, status")
        rows = cursor.fetchall()

        print("JOB SUMMARY BY TYPE AND STATUS:")
        print("-" * 60)
        print(f"{'Type':<25} | {'Status':<15} | {'Count'}")
        print("-" * 60)
        for row in rows:
            print(f"{row[0]:<25} | {row[1]:<15} | {row[2]}")
        print("-" * 60)

    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    count_jobs()
