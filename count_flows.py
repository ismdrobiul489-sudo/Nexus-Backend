import sqlite3
import os

db_path = "e:/coding/Antigravity/fba---facebook-automation-assistant/backend/nexus_v2.db"

def count_flows():
    if not os.path.exists(db_path):
        print("Database missing.")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT COUNT(*) FROM flowconfig")
        count = cursor.fetchone()[0]
        print(f"FLOW_CONFIG_COUNT: {count}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    count_flows()
