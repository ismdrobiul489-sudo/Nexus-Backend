import sqlite3
import os
from datetime import datetime

nexus_db = "e:/coding/Antigravity/fba---facebook-automation-assistant/backend/nexus_v2.db"
aps_db = "e:/coding/Antigravity/fba---facebook-automation-assistant/backend/jobs.sqlite"

def audit_schedules():
    if not os.path.exists(nexus_db) or not os.path.exists(aps_db):
        print("Error: Database files missing.")
        return

    # 1. Get Flow Names
    flow_map = {}
    try:
        conn = sqlite3.connect(nexus_db)
        cursor = conn.cursor()
        cursor.execute("SELECT id, name FROM flowconfig")
        for row in cursor.fetchall():
            flow_map[row[0]] = row[1]
        conn.close()
    except Exception as e:
        print(f"Error reading nexus_v2: {e}")

    # 2. Get APScheduler Jobs
    try:
        conn = sqlite3.connect(aps_db)
        cursor = conn.cursor()
        cursor.execute("SELECT id, next_run_time FROM apscheduler_jobs")
        rows = cursor.fetchall()
        conn.close()

        print("\n--- DATABASE AUDIT vs FRONT-END LIST ---")
        
        found_jobs = []
        for row in rows:
            full_id, next_run = row
            try:
                # Assuming next_run is a timestamp (UTC)
                dt = datetime.fromtimestamp(next_run)
                time_str = dt.strftime('%H:%M')
            except:
                time_str = "Unknown"

            flow_id = full_id.split('_slot_')[0] if '_slot_' in full_id else full_id
            name = flow_map.get(flow_id, full_id)
            found_jobs.append((name.lower().strip(), time_str))

        # Human-friendly comparison
        print(f"{'Flow Name':<30} | {'DB Time':<10}")
        print("-" * 45)
        for name, t in sorted(found_jobs):
            if any(x in name for x in ['youtube', 'reel', 'short', 'quiz', 'text']):
                print(f"{name:<30} | {t:<10}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    audit_schedules()
