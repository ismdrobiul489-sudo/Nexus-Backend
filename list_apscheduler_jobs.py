import sqlite3
import os

# APScheduler uses SQLAlchemyJobStore with jobs.sqlite
db_path = "e:/coding/Antigravity/fba---facebook-automation-assistant/backend/jobs.sqlite"

def list_apscheduler_jobs():
    if not os.path.exists(db_path):
        print(f"Error: APScheduler database not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # APScheduler table is usually 'apscheduler_jobs'
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='apscheduler_jobs'")
        if not cursor.fetchone():
            print("Error: 'apscheduler_jobs' table not found.")
            return

        cursor.execute("SELECT id, next_run_time FROM apscheduler_jobs")
        rows = cursor.fetchall()

        if not rows:
            print("\n📭 No jobs scheduled in APScheduler.")
            return

        print(f"\n⏰ Found {len(rows)} Scheduled Jobs in APScheduler:")
        print("-" * 60)
        for row in rows:
            job_id, next_run = row
            # Convert next_run (if timestamp) or just print raw
            print(f"ID: {job_id:30} | Next Run: {next_run}")
        print("-" * 60)

    except Exception as e:
        print(f"Error querying APScheduler db: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    list_apscheduler_jobs()
