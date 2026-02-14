import shutil
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict
from utils.file_ops import FileOperations
from database import db
from config import config

class BackupManager:
    """Manage file backups with retention policies"""
    
    def __init__(self):
        self.backup_dir = Path("data/backups")
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.file_ops = FileOperations()
    
    async def create_backup(self, file_path: str) -> str:
        """
        Create a timestamped backup of a file
        
        Args:
            file_path: Path to file to backup
        
        Returns:
            Path to backup file
        """
        path = Path(file_path)
        
        if not path.exists():
            raise FileNotFoundError(f"Cannot backup non-existent file: {file_path}")
        
        # Generate backup filename
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        backup_name = f"{path.stem}.{timestamp}.backup{path.suffix}"
        backup_path = self.backup_dir / backup_name
        
        # Copy file
        shutil.copy2(path, backup_path)
        
        # Calculate hash
        file_hash = self.file_ops.calculate_hash(str(backup_path))
        
        # Record in database
        await db.add_backup_record(
            file_path=str(path),
            backup_path=str(backup_path),
            file_hash=file_hash
        )
        
        return str(backup_path)
    
    async def list_backups(
        self,
        file_path: str = None,
        limit: int = 50
    ) -> List[Dict]:
        """
        List available backups
        
        Args:
            file_path: Optional - filter by original file
            limit: Maximum number to return
        
        Returns:
            List of backup records
        """
        backups = await db.get_backups(file_path)
        return backups[:limit]
    
    async def cleanup_old_backups(self, retention_days: int = None):
        """
        Remove backups older than retention period and enforce per-file limits
        
        Args:
            retention_days: Days to keep backups (from config if not specified)
        """
        if retention_days is None:
            retention_days = config.get('auto_apply.backup_retention_days', 30)
        
        max_per_file = config.get('auto_apply.max_backups_per_file', 10)
        
        cutoff_date = datetime.now() - timedelta(days=retention_days)
        
        # Get all backups
        backups = await db.get_backups()
        
        removed_count = 0
        
        # Phase 1: Remove backups older than retention period
        remaining_backups = []
        for backup in backups:
            created_at = datetime.fromisoformat(backup['created_at'])
            
            if created_at < cutoff_date:
                # Remove file
                backup_path = Path(backup['backup_path'])
                if backup_path.exists():
                    backup_path.unlink()
                    removed_count += 1
            else:
                remaining_backups.append(backup)
        
        # Phase 2: Enforce max_backups_per_file limit
        from collections import defaultdict
        backups_by_file = defaultdict(list)
        
        for backup in remaining_backups:
            backups_by_file[backup['file_path']].append(backup)
        
        for file_path, file_backups in backups_by_file.items():
            # Sort by creation date descending (newest first)
            file_backups.sort(
                key=lambda b: b['created_at'],
                reverse=True
            )
            
            # Remove oldest beyond the limit
            for old_backup in file_backups[max_per_file:]:
                backup_path = Path(old_backup['backup_path'])
                if backup_path.exists():
                    backup_path.unlink()
                    removed_count += 1
        
        return removed_count
    
    def get_backup_size(self) -> Dict[str, int]:
        """
        Get total size of backups
        
        Returns:
            Dict with count and total bytes
        """
        backup_files = list(self.backup_dir.glob("*.backup.*"))
        
        total_size = sum(f.stat().st_size for f in backup_files if f.is_file())
        
        return {
            "count": len(backup_files),
            "total_bytes": total_size,
            "total_mb": round(total_size / (1024 * 1024), 2)
        }
    
    async def verify_backup(self, backup_path: str) -> bool:
        """
        Verify backup integrity using stored hash
        
        Args:
            backup_path: Path to backup file
        
        Returns:
            True if backup is valid
        """
        backups = await db.get_backups()
        backup_record = next(
            (b for b in backups if b['backup_path'] == backup_path),
            None
        )
        
        if not backup_record:
            return False
        
        # Calculate current hash
        current_hash = self.file_ops.calculate_hash(backup_path)
        
        # Compare with stored hash
        return current_hash == backup_record['file_hash']
    
    async def restore_backup(self, backup_path: str, target_path: str) -> bool:
        """
        Restore a file from its backup
        
        Args:
            backup_path: Path to the backup file
            target_path: Path where the file should be restored to
        
        Returns:
            True if restore succeeded
        """
        backup_file = Path(backup_path)
        target_file = Path(target_path)
        
        if not backup_file.exists():
            raise FileNotFoundError(f"Backup file not found: {backup_path}")
        
        # Create a backup of the current file before overwriting
        if target_file.exists():
            await self.create_backup(str(target_file))
        
        # Restore
        shutil.copy2(str(backup_file), str(target_file))
        return True

