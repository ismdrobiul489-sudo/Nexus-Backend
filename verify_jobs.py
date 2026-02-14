import sqlite3
import os
from datetime import datetime

def check_db():
    print(f"--- SYSTEM TIME ---")
    print(f"Local Time: {datetime.now()}")
    print(f"UTC Time:   {datetime.utcnow()}")
    print("-" * 20)

    nexus_db = "nexus_v2.db"
    aps_db = "jobs.sqlite"

    if os.path.exists(nexus_db):
        print(f"--- NEXUS_V2 JOBS (Queue) ---")
        try:
            conn = sqlite3.connect(nexus_db)
            cursor = conn.cursor()
            cursor.execute("SELECT id, type, status, scheduled_at FROM job ORDER BY created_at DESC LIMIT 10")
            rows = cursor.fetchall()
            for row in rows:
                print(row)
            conn.close()
        except Exception as e:
            print(f"Error reading {nexus_db}: {e}")
    else:
        print(f"MISSING: {nexus_db}")

    if os.path.exists(aps_db):
        print(f"\n--- APSCHEDULER TRIGGERS ---")
        try:
            conn = sqlite3.connect(aps_db)
            cursor = conn.cursor()
            cursor.execute("SELECT id, next_run_time FROM apscheduler_jobs")
            rows = cursor.fetchall()
            for row in rows:
                job_id, next_run = row
                try:
                    dt = datetime.fromtimestamp(next_run)
                    print(f"ID: {job_id} | Next Run: {dt} (Timestamp: {next_run})")
                except:
                    print(f"ID: {job_id} | Next Run Raw: {next_run}")
            conn.close()
        except Exception as e:
            print(f"Error reading {aps_db}: {e}")
    else:
        print(f"MISSING: {aps_db}")

if __name__ == "__main__":
    check_db()
