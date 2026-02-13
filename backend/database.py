import aiosqlite
import json
from typing import List, Dict, Optional
from datetime import datetime
from config import config

class Database:
    """Async database operations for STCM"""
    
    def __init__(self, db_path: str = None):
        self.db_path = db_path or config.db_path
    
    async def execute(self, query: str, params: tuple = ()):
        """Execute a single query"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(query, params)
            await db.commit()
    
    async def fetch_one(self, query: str, params: tuple = ()) -> Optional[Dict]:
        """Fetch a single row"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(query, params) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None
    
    async def fetch_all(self, query: str, params: tuple = ()) -> List[Dict]:
        """Fetch all rows"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(query, params) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
    
    # Entity Queue Operations
    
    async def add_entity(
        self,
        entity_type: str,
        entity_name: str,
        entity_data: Dict,
        target_file: str,
        source_messages: str,
        confidence_score: float
    ) -> int:
        """Add entity to review queue"""
        query = """
        INSERT INTO entity_queue (
            entity_type, entity_name, entity_data, target_file,
            source_messages, confidence_score
        ) VALUES (?, ?, ?, ?, ?, ?)
        """
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                query,
                (entity_type, entity_name, json.dumps(entity_data),
                 target_file, source_messages, confidence_score)
            )
            await db.commit()
            return cursor.lastrowid
    
    async def get_pending_entities(self, entity_type: str = None) -> List[Dict]:
        """Get all pending entities, optionally filtered by type"""
        if entity_type:
            query = "SELECT * FROM entity_queue WHERE status = 'pending' AND entity_type = ? ORDER BY confidence_score DESC"
            params = (entity_type,)
        else:
            query = "SELECT * FROM entity_queue WHERE status = 'pending' ORDER BY confidence_score DESC"
            params = ()
        
        entities = await self.fetch_all(query, params)
        
        # Parse JSON data
        for entity in entities:
            entity['entity_data'] = json.loads(entity['entity_data'])
        
        return entities
    
    async def update_entity_status(
        self,
        entity_id: int,
        status: str,
        reviewed_by: str = "user"
    ):
        """Update entity status (approve/reject)"""
        query = """
        UPDATE entity_queue 
        SET status = ?, reviewed_at = ?, reviewed_by = ?
        WHERE id = ?
        """
        await self.execute(
            query,
            (status, datetime.now().isoformat(), reviewed_by, entity_id)
        )
    
    async def update_entity_data(
        self,
        entity_id: int,
        entity_data: Dict
    ):
        """Update entity data (for edits)"""
        query = "UPDATE entity_queue SET entity_data = ? WHERE id = ?"
        await self.execute(query, (json.dumps(entity_data), entity_id))
    
    # Scan History Operations
    
    async def add_scan_record(
        self,
        chat_file: str,
        character_file: str,
        messages_scanned: int,
        entities_found: int,
        status: str,
        error_message: str = None
    ) -> int:
        """Record a scan in history"""
        query = """
        INSERT INTO scan_history (
            chat_file, character_file, messages_scanned,
            entities_found, status, error_message
        ) VALUES (?, ?, ?, ?, ?, ?)
        """
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                query,
                (chat_file, character_file, messages_scanned,
                 entities_found, status, error_message)
            )
            await db.commit()
            return cursor.lastrowid
    
    async def get_scan_history(self, limit: int = 50) -> List[Dict]:
        """Get recent scan history"""
        query = "SELECT * FROM scan_history ORDER BY scan_date DESC LIMIT ?"
        return await self.fetch_all(query, (limit,))
    
    async def get_last_scan(self, chat_file: str) -> Optional[Dict]:
        """Get the most recent scan for a chat file"""
        query = """
        SELECT * FROM scan_history 
        WHERE chat_file = ? 
        ORDER BY scan_date DESC 
        LIMIT 1
        """
        return await self.fetch_one(query, (chat_file,))
    
    # Update History Operations
    
    async def add_update_record(
        self,
        entity_id: int,
        entity_type: str,
        entity_name: str,
        target_file: str,
        action: str,
        old_value: Dict = None,
        new_value: Dict = None
    ):
        """Record an applied update"""
        query = """
        INSERT INTO update_history (
            entity_id, entity_type, entity_name, target_file,
            action, old_value, new_value
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        await self.execute(
            query,
            (entity_id, entity_type, entity_name, target_file, action,
             json.dumps(old_value) if old_value else None,
             json.dumps(new_value) if new_value else None)
        )
    
    async def get_update_history(self, limit: int = 100) -> List[Dict]:
        """Get recent update history"""
        query = "SELECT * FROM update_history ORDER BY applied_at DESC LIMIT ?"
        return await self.fetch_all(query, (limit,))
    
    # Backup Operations
    
    async def add_backup_record(
        self,
        file_path: str,
        backup_path: str,
        file_hash: str
    ):
        """Record a file backup"""
        query = """
        INSERT INTO file_backups (file_path, backup_path, file_hash)
        VALUES (?, ?, ?)
        """
        await self.execute(query, (file_path, backup_path, file_hash))
    
    async def get_backups(self, file_path: str = None) -> List[Dict]:
        """Get backup history, optionally for a specific file"""
        if file_path:
            query = "SELECT * FROM file_backups WHERE file_path = ? ORDER BY created_at DESC"
            params = (file_path,)
        else:
            query = "SELECT * FROM file_backups ORDER BY created_at DESC LIMIT 100"
            params = ()
        
        return await self.fetch_all(query, params)
    
    # Chat Mapping Operations
    
    async def add_chat_mapping(
        self,
        chat_file: str,
        character_file: str,
        persona_file: str = None
    ):
        """Add or update chat to character mapping"""
        query = """
        INSERT INTO chat_mappings (chat_file, character_file, persona_file)
        VALUES (?, ?, ?)
        ON CONFLICT(chat_file) DO UPDATE SET
            character_file = excluded.character_file,
            persona_file = excluded.persona_file,
            updated_at = CURRENT_TIMESTAMP
        """
        await self.execute(query, (chat_file, character_file, persona_file))
    
    async def get_chat_mapping(self, chat_file: str) -> Optional[Dict]:
        """Get character file for a chat file"""
        query = "SELECT * FROM chat_mappings WHERE chat_file = ?"
        return await self.fetch_one(query, (chat_file,))
    
    async def get_all_chat_mappings(self) -> List[Dict]:
        """Get all chat mappings"""
        query = "SELECT * FROM chat_mappings ORDER BY updated_at DESC"
        return await self.fetch_all(query)

# Global database instance
db = Database()
