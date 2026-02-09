import sqlite3
import os
from datetime import datetime

aps_db = "e:/coding/Antigravity/fba---facebook-automation-assistant/backend/jobs.sqlite"

def detailed_aps_audit():
    if not os.path.exists(aps_db):
        print("Error: APScheduler database missing.")
        return

    try:
        conn = sqlite3.connect(aps_db)
        cursor = conn.cursor()
        cursor.execute("SELECT id, next_run_time FROM apscheduler_jobs")
        rows = cursor.fetchall()
        conn.close()

        print(f"DETAILED APSCHEDULER AUDIT (TOTAL: {len(rows)})")
        print("-" * 80)
        print(f"{'#':<3} | {'Job ID':<45} | {'Next Run (UTC)'}")
        print("-" * 80)
        
        for i, row in enumerate(rows, 1):
            full_id, next_run = row
            try:
                dt = datetime.fromtimestamp(next_run)
                time_str = dt.strftime('%Y-%m-%d %H:%M:%S')
            except:
                time_str = str(next_run)
                
            print(f"{i:<3} | {full_id:<45} | {time_str}")
        print("-" * 80)

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    detailed_aps_audit()
