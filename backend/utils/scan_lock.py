import asyncio
from typing import Dict, Optional
from datetime import datetime

class ScanLockManager:
    """
    Prevent concurrent scans of the same chat file
    
    Ensures only one scan runs at a time per chat
    """
    
    def __init__(self):
        self.active_scans: Dict[str, datetime] = {}
        self._lock = asyncio.Lock()
    
    async def acquire_scan_lock(self, chat_file: str) -> bool:
        """
        Try to acquire lock for scanning a chat file
        
        Returns:
            True if lock acquired, False if scan already in progress
        """
        async with self._lock:
            if chat_file in self.active_scans:
                # Check if scan is stale (running >30 minutes)
                elapsed = (datetime.now() - self.active_scans[chat_file]).seconds
                if elapsed < 1800:  # 30 minutes
                    return False
                # Stale lock, remove it
                del self.active_scans[chat_file]
            
            self.active_scans[chat_file] = datetime.now()
            return True
    
    async def release_scan_lock(self, chat_file: str):
        """Release scan lock"""
        async with self._lock:
            if chat_file in self.active_scans:
                del self.active_scans[chat_file]
    
    async def is_scan_active(self, chat_file: str) -> bool:
        """Check if scan is currently active for a chat"""
        async with self._lock:
            return chat_file in self.active_scans
    
    def get_active_scans(self) -> Dict[str, datetime]:
        """Get all active scans"""
        return self.active_scans.copy()


# Global instance
scan_lock_manager = ScanLockManager()


# Usage in routes.py:
# if not await scan_lock_manager.acquire_scan_lock(chat_file):
#     raise HTTPException(409, "Scan already in progress for this chat")
# 
# try:
#     await run_scan(...)
# finally:
#     await scan_lock_manager.release_scan_lock(chat_file)
