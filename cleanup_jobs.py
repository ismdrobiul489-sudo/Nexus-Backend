import sqlite3
import os

nexus_db = "e:/coding/Antigravity/fba---facebook-automation-assistant/backend/nexus_v2.db"
aps_db = "e:/coding/Antigravity/fba---facebook-automation-assistant/backend/jobs.sqlite"

def cleanup_orphaned_jobs():
    if not os.path.exists(nexus_db) or not os.path.exists(aps_db):
        print("Missing DB files.")
        return

    # 1. Get valid flow IDs from FlowConfig
    conn = sqlite3.connect(nexus_db)
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM flowconfig")
    valid_flow_ids = {row[0] for row in cursor.fetchall()}
    conn.close()

    # 2. Identify and delete orbits in APS
    conn = sqlite3.connect(aps_db)
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM apscheduler_jobs")
    aps_ids = [row[0] for row in cursor.fetchall()]

    to_delete = []
    for full_id in aps_ids:
        # Keep system jobs
        if full_id.startswith("system_"):
            continue
            
        base_id = full_id.split("_slot_")[0] if "_slot_" in full_id else full_id
        if base_id not in valid_flow_ids:
            to_delete.append(full_id)

    if not to_delete:
        print("No orphaned jobs found.")
    else:
        print(f"Total orphaned jobs identified for deletion: {len(to_delete)}")
        for jid in to_delete:
            cursor.execute("DELETE FROM apscheduler_jobs WHERE id = ?", (jid,))
            print(f"Deleted: {jid}")
        conn.commit()
        print("Cleanup complete.")

    conn.close()

if __name__ == "__main__":
    cleanup_orphaned_jobs()
