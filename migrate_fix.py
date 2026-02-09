import sqlite3

def migrate_db():
    conn = sqlite3.connect('nexus_v2.db')
    cursor = conn.cursor()
    
    try:
        print("Checking flowconfig table...")
        cursor.execute("PRAGMA table_info(flowconfig)")
        columns = [info[1] for info in cursor.fetchall()]
        
        if 'last_run_at' not in columns:
            print("Adding missing column 'last_run_at'...")
            cursor.execute("ALTER TABLE flowconfig ADD COLUMN last_run_at DATETIME")
            conn.commit()
            print("Migration successful: Added 'last_run_at'")
        else:
            print("Column 'last_run_at' already exists.")
            
    except Exception as e:
        print(f"Migration failed: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_db()
