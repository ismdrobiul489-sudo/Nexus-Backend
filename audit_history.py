import sqlite3
import os
from datetime import datetime

db_path = "e:/coding/Antigravity/fba---facebook-automation-assistant/backend/nexus_v2.db"

def audit_history():
    if not os.path.exists(db_path):
        print(f"Error: Database file not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Fetch all jobs to see history
        cursor.execute("""
            SELECT type, status, scheduled_at, created_at, error 
            FROM job 
            ORDER BY created_at DESC 
            LIMIT 50
        """)
        
        rows = cursor.fetchall()

        if not rows:
            print("No job history found.")
            return

        print(f"\n📑 Last 50 Jobs (History):")
        print("-" * 120)
        print(f"{'Created At':<20} | {'Type':<15} | {'Status':<10} | {'Scheduled At':<20} | {'Error'}")
        print("-" * 120)
        for row in rows:
            created, jtype, status, scheduled, error = row
            err_msg = (error[:40] + "...") if error else "None"
            print(f"{created:<20} | {jtype:<15} | {status:<10} | {scheduled:<20} | {err_msg}")
        print("-" * 120)

    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    audit_history()
