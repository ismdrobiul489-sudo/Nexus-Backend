import sqlite3
import os
from datetime import datetime

nexus_db = "e:/coding/Antigravity/fba---facebook-automation-assistant/backend/nexus_v2.db"
aps_db = "e:/coding/Antigravity/fba---facebook-automation-assistant/backend/jobs.sqlite"

def list_scheduled_flows():
    if not os.path.exists(nexus_db) or not os.path.exists(aps_db):
        print("Error: Database files missing.")
        return

    # 1. Get Flow Names from nexus_v2.db
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

        if not rows:
            print("No active schedules found.")
            return

        print(f"REPORT: Found {len(rows)} Active Schedules")
        print("-" * 100)
        print(f"{'Flow Name/ID':<40} | {'Next Run Time (UTC)':<25} | {'Slot'}")
        print("-" * 100)
        
        system_jobs = []
        user_flows = []

        for row in rows:
            full_id, next_run = row
            
            try:
                dt = datetime.fromtimestamp(next_run)
                time_str = dt.strftime('%Y-%m-%d %H:%M:%S')
            except:
                time_str = str(next_run)

            flow_id = full_id.split('_slot_')[0] if '_slot_' in full_id else full_id
            name = flow_map.get(flow_id, full_id)
            slot = full_id.split('_slot_')[1] if '_slot_' in full_id else "N/A"

            if full_id in ['system_job_processor', 'system_cleanup']:
                system_jobs.append((name, time_str, slot))
            else:
                user_flows.append((name, time_str, slot))

        user_flows.sort(key=lambda x: x[0])

        for name, time_str, slot in user_flows:
            print(f"{name:<40} | {time_str:<25} | Slot: {slot}")
        
        if system_jobs:
            print("\nCORE SYSTEM JOBS:")
            for name, time_str, slot in system_jobs:
                print(f"{name:<40} | {time_str:<25} | {slot}")

        print("-" * 100)

    except Exception as e:
        print(f"Error querying APScheduler: {e}")

if __name__ == "__main__":
    list_scheduled_flows()
