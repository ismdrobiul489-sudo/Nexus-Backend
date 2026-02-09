import sqlite3
import os
import json
from datetime import datetime

db_path = "e:/coding/Antigravity/fba---facebook-automation-assistant/backend/nexus_v2.db"

def list_jobs():
    if not os.path.exists(db_path):
        print(f"Error: Database file not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Check if 'job' table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='job'")
        if not cursor.fetchone():
            print("Error: 'job' table not found in database.")
            return

        # Fetch only PENDING or PROCESSING jobs to keep output relevant
        cursor.execute("""
            SELECT id, type, status, scheduled_at, created_at, attempts, payload 
            FROM job 
            WHERE status IN ('pending', 'processing')
            ORDER BY scheduled_at ASC
        """)
        
        rows = cursor.fetchall()

        if not rows:
            print("\n📭 No pending or processing jobs found in the database.")
            return

        print(f"\n📋 Found {len(rows)} Active/Pending Jobs:")
        print("-" * 100)
        for row in rows:
            job_id, job_type, status, scheduled_at, created_at, attempts, payload = row
            
            # Optional: parse payload for niche if available (standard in video flows)
            niche = "N/A"
            try:
                p_dict = json.loads(payload)
                niche = p_dict.get('niche', 'N/A')
            except:
                pass

            print(f"ID: {job_id[:8]}... | Type: {job_type:15} | Status: {status:10} | Scheduled: {scheduled_at} | Niche: {niche}")
        print("-" * 100)

    except Exception as e:
        print(f"Error querying database: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    list_jobs()
