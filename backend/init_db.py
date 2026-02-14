import sqlite3
import os
from pathlib import Path

def init_database(db_path: str = "data/stcm.db"):
    """Initialize the STCM database with all required tables"""
    
    # Ensure directory exists
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Configuration table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS config (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # Scan history
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS scan_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        scan_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        chat_file TEXT NOT NULL,
        character_file TEXT,
        messages_scanned INTEGER,
        entities_found INTEGER,
        status TEXT CHECK(status IN ('completed', 'failed', 'partial')),
        error_message TEXT
    )
    """)
    
    # Entity queue (pending review)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS entity_queue (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        entity_type TEXT NOT NULL CHECK(entity_type IN ('npc', 'faction', 'location', 'item', 'alias', 'stat')),
        entity_name TEXT NOT NULL,
        entity_data TEXT NOT NULL,
        target_file TEXT NOT NULL,
        source_messages TEXT,
        confidence_score REAL,
        status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'approved', 'rejected')),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        reviewed_at TIMESTAMP,
        reviewed_by TEXT
    )
    """)
    
    # Applied updates history
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS update_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        entity_id INTEGER,
        entity_type TEXT,
        entity_name TEXT,
        target_file TEXT,
        action TEXT CHECK(action IN ('added', 'updated', 'merged')),
        old_value TEXT,
        new_value TEXT,
        applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (entity_id) REFERENCES entity_queue(id)
    )
    """)
    
    # File backups
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS file_backups (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        file_path TEXT NOT NULL,
        backup_path TEXT NOT NULL,
        file_hash TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # Scheduled jobs
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS scheduled_jobs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_name TEXT NOT NULL,
        schedule TEXT NOT NULL,
        enabled BOOLEAN DEFAULT 1,
        last_run TIMESTAMP,
        next_run TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # Chat to character mappings
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS chat_mappings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_file TEXT NOT NULL UNIQUE,
        character_file TEXT NOT NULL,
        persona_file TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # Processing checkpoints (track what's been scanned)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS processing_checkpoints (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_file TEXT NOT NULL UNIQUE,
        last_processed_index INTEGER NOT NULL DEFAULT 0,
        last_processed_timestamp TEXT,
        total_messages INTEGER,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # Create indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_entity_status ON entity_queue(status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_entity_type ON entity_queue(entity_type)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_scan_date ON scan_history(scan_date DESC)")
    
    conn.commit()
    conn.close()
    
    print(f"✓ Database initialized at {db_path}")

if __name__ == "__main__":
    init_database()
