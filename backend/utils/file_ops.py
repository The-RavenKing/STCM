import json
import hashlib
from pathlib import Path
from typing import Dict, Any
import shutil
from datetime import datetime

class FileOperations:
    """Safe file read/write operations with atomic writes"""
    
    @staticmethod
    async def read_json(file_path: str) -> Dict[str, Any]:
        """Safely read a JSON file"""
        path = Path(file_path)
        
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    @staticmethod
    async def write_json(
        file_path: str,
        data: Dict[str, Any],
        create_backup: bool = True
    ) -> bool:
        """
        Safely write JSON file with atomic operation
        
        Args:
            file_path: Path to file
            data: Data to write
            create_backup: Whether to backup first
        
        Returns:
            Success boolean
        """
        path = Path(file_path)
        
        # Create backup if file exists
        if create_backup and path.exists():
            await FileOperations.create_backup(file_path)
        
        # Write to temporary file first
        temp_path = path.with_suffix('.tmp')
        
        try:
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            # Atomic replace
            shutil.move(str(temp_path), str(path))
            
            return True
            
        except Exception as e:
            # Clean up temp file if it exists
            if temp_path.exists():
                temp_path.unlink()
            raise e
    
    @staticmethod
    async def create_backup(file_path: str) -> str:
        """
        Create a backup of a file
        
        Args:
            file_path: Path to file to backup
        
        Returns:
            Path to backup file
        """
        path = Path(file_path)
        
        if not path.exists():
            raise FileNotFoundError(f"Cannot backup non-existent file: {file_path}")
        
        # Create backups directory
        backup_dir = Path("data/backups")
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate backup filename with timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        backup_name = f"{path.stem}.{timestamp}.backup{path.suffix}"
        backup_path = backup_dir / backup_name
        
        # Copy file
        shutil.copy2(path, backup_path)
        
        return str(backup_path)
    
    @staticmethod
    def calculate_hash(file_path: str) -> str:
        """Calculate SHA256 hash of a file"""
        sha256 = hashlib.sha256()
        
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b''):
                sha256.update(chunk)
        
        return sha256.hexdigest()
    
    @staticmethod
    def validate_json_structure(data: Dict, required_keys: list) -> bool:
        """Validate that a JSON structure has required keys"""
        return all(key in data for key in required_keys)
    
    @staticmethod
    async def safe_read_or_create(
        file_path: str,
        default_data: Dict
    ) -> Dict[str, Any]:
        """Read JSON file or create with default data if it doesn't exist"""
        path = Path(file_path)
        
        if not path.exists():
            # Create parent directories
            path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write default data
            await FileOperations.write_json(file_path, default_data, create_backup=False)
            return default_data
        
        return await FileOperations.read_json(file_path)
