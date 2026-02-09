import sqlite3
import os

nexus_db = "e:/coding/Antigravity/fba---facebook-automation-assistant/backend/nexus_v2.db"
aps_db = "e:/coding/Antigravity/fba---facebook-automation-assistant/backend/jobs.sqlite"

def map_jobs_to_flows():
    if not os.path.exists(nexus_db) or not os.path.exists(aps_db):
        print("Missing DB files.")
        return

    # 1. Get Flow Map
    flow_map = {}
    conn = sqlite3.connect(nexus_db)
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM flowconfig")
    for row in cursor.fetchall():
        fid, fname = row
        flow_map[fid] = fname
    conn.close()

    # 2. Get APS Jobs
    conn = sqlite3.connect(aps_db)
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM apscheduler_jobs")
    aps_ids = [row[0] for row in cursor.fetchall()]
    conn.close()

    print("MAPPING APS JOBS TO FLOWS:")
    print("-" * 60)
    
    seen_flows = {}
    system_jobs = []
    
    for full_id in aps_ids:
        if full_id.startswith("system_"):
            system_jobs.append(full_id)
            continue
            
        base_id = full_id.split("_slot_")[0] if "_slot_" in full_id else full_id
        name = flow_map.get(base_id, f"Unknown ({base_id})")
        
        if name not in seen_flows:
            seen_flows[name] = 0
        seen_flows[name] += 1

    print(f"{'Flow Name':<40} | {'Total Slots (Schedules)'}")
    print("-" * 60)
    for name, count in seen_flows.items():
        print(f"{name:<40} | {count}")
    
    print("-" * 60)
    print(f"System Jobs: {len(system_jobs)}")
    print(f"Unique Flows in Jobs: {len(seen_flows)}")
    print(f"Total entries: {len(aps_ids)}")

if __name__ == "__main__":
    map_jobs_to_flows()
