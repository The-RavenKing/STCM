import json
from typing import Dict, Optional, List
from pathlib import Path
from utils.file_ops import FileOperations
from database import db
import re
import unicodedata

class LorebookUpdater:
    """Update character lorebooks with new entities"""
    
    def __init__(self):
        self.file_ops = FileOperations()
    
    async def add_entry(
        self,
        character_file: str,
        entity: Dict,
        entity_type: str
    ) -> bool:
        """
        Add a new entry to character lorebook
        
        Args:
            character_file: Path to character JSON file
            entity: Entity data to add
            entity_type: Type of entity (npc, faction, location, item)
        
        Returns:
            Success boolean
        """
        # Load character file
        char_data = await self.file_ops.read_json(character_file)
        
        # Ensure character_book structure exists
        if "data" not in char_data:
            char_data["data"] = {}
        
        if "character_book" not in char_data["data"]:
            char_data["data"]["character_book"] = {
                "name": "Campaign Lorebook",
                "entries": []
            }
        
        # Check for duplicates
        existing_entry = self._find_existing_entry(
            char_data["data"]["character_book"]["entries"],
            entity["name"]
        )
        
        if existing_entry:
            # Merge instead of duplicate
            return await self._merge_entry(
                character_file,
                char_data,
                existing_entry,
                entity,
                entity_type
            )
        
        # Create new entry
        new_entry = self._create_lorebook_entry(entity, entity_type)
        
        # Add to lorebook
        char_data["data"]["character_book"]["entries"].append(new_entry)
        
        # Save
        await self.file_ops.write_json(character_file, char_data)
        
        return True
    
    def _find_existing_entry(
        self,
        entries: List[Dict],
        entity_name: str
    ) -> Optional[Dict]:
        """Check if an entity already exists in the lorebook"""
        name_lower = entity_name.lower()
        
        for entry in entries:
            # Check if name is in the keys
            keys = entry.get("keys", [])
            if any(name_lower == key.lower() for key in keys):
                return entry
            
            # Check content
            content = entry.get("content", "").lower()
            if name_lower in content:
                return entry
        
        return None
    
    async def _merge_entry(
        self,
        character_file: str,
        char_data: Dict,
        existing_entry: Dict,
        new_entity: Dict,
        entity_type: str
    ) -> bool:
        """Merge new entity information with existing entry"""
        # Update content with new information
        old_content = existing_entry.get("content", "")
        new_info = self._format_entity_content(new_entity, entity_type)
        
        # Append new information if it's not already there
        if new_info not in old_content:
            existing_entry["content"] = f"{old_content}\n\n[Updated]\n{new_info}"
        
        # Add any new keys
        existing_keys = set(existing_entry.get("keys", []))
        new_keys = set(self._generate_keys(new_entity["name"]))
        
        all_keys = list(existing_keys | new_keys)
        existing_entry["keys"] = all_keys
        
        # Save
        await self.file_ops.write_json(character_file, char_data)
        
        return True
    
    def _create_lorebook_entry(self, entity: Dict, entity_type: str) -> Dict:
        """Format entity as a lorebook entry"""
        entry_id = self._generate_entry_id(entity["name"])
        
        return {
            "id": entry_id,
            "keys": self._generate_keys(entity["name"]),
            "secondary_keys": [],
            "comment": f"{entity_type.upper()} - Auto-generated",
            "content": self._format_entity_content(entity, entity_type),
            "constant": False,
            "selective": True,
            "insertion_order": 100,
            "enabled": True,
            "position": "before_char",
            "use_regex": True,
            "extensions": {
                "position": 0,
                "exclude_recursion": False,
                "display_index": entry_id,
                "probability": 100,
                "useProbability": True,
                "depth": 4,
                "selectiveLogic": 0,
                "prevent_recursion": False,
                "delay_until_recursion": False,
                "scan_depth": None,
                "match_whole_words": None,
                "use_group_scoring": False,
                "case_sensitive": False,
                "automation_id": "",
                "role": 0,
                "vectorized": False,
                "sticky": 0,
                "cooldown": 0,
                "delay": 0
            }
        }
    
    def _generate_entry_id(self, name: str) -> int:
        """Generate a unique-ish ID from name"""
        # Simple hash-based ID
        return abs(hash(name)) % 1000000
    
    def _sanitize_for_keys(self, name: str) -> str:
        """Strip emoji/symbols from name, preserving letters, numbers, and spaces"""
        return ''.join(
            c for c in name
            if unicodedata.category(c)[0] in ('L', 'N', 'Z')
        ).strip()
    
    def _generate_keys(self, name: str) -> List[str]:
        """Generate search keys for an entity"""
        # Sanitize the name first (strip emoji/symbols)
        sanitized = self._sanitize_for_keys(name)
        base_name = sanitized if sanitized else name
        
        keys = [base_name.lower()]
        
        # Add the original name too if different
        if name.lower() != base_name.lower():
            keys.append(name.lower())
        
        # Add variations
        # First name if multiple words
        parts = base_name.split()
        if len(parts) > 1:
            keys.append(parts[0].lower())
            keys.append(parts[-1].lower())
        
        # Add without special characters
        clean_name = re.sub(r'[^a-zA-Z0-9\s]', '', base_name).lower()
        if clean_name != base_name.lower():
            keys.append(clean_name)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_keys = []
        for key in keys:
            if key not in seen and key:
                seen.add(key)
                unique_keys.append(key)
        
        return unique_keys
    
    def _format_entity_content(self, entity: Dict, entity_type: str) -> str:
        """Format entity data as lorebook content"""
        name = entity.get("name", "Unknown")
        
        if entity_type == "npc":
            content = f"{name}"
            
            if entity.get("description"):
                content += f" is {entity['description']}."
            
            if entity.get("relationship"):
                content += f"\n\nRelationship to {{{{user}}}}: {entity['relationship']}"
            
            if entity.get("source_context"):
                content += f"\n\n[Context: {entity['source_context']}]"
            
            return content
        
        elif entity_type == "faction":
            content = f"{name}"
            
            if entity.get("description"):
                content += f" is {entity['description']}."
            
            if entity.get("goals"):
                content += f"\n\nGoals: {entity['goals']}"
            
            if entity.get("leadership"):
                content += f"\nLeadership: {entity['leadership']}"
            
            if entity.get("territory"):
                content += f"\nTerritory: {entity['territory']}"
            
            if entity.get("relationship"):
                content += f"\n\nRelationship to {{{{user}}}}: {entity['relationship']}"
            
            return content
        
        elif entity_type == "location":
            content = f"{name}"
            
            if entity.get("description"):
                content += f" - {entity['description']}."
            
            if entity.get("significance"):
                content += f"\n\nSignificance: {entity['significance']}"
            
            return content
        
        elif entity_type == "item":
            content = f"{name}"
            
            if entity.get("description"):
                content += f" - {entity['description']}."
            
            if entity.get("properties"):
                content += f"\n\nProperties: {entity['properties']}"
            
            return content
        
        elif entity_type == "mythology":
            content = f"{name}"
            
            if entity.get("category"):
                content += f" [{entity['category']}]"
            
            if entity.get("description"):
                content += f" - {entity['description']}."
            
            if entity.get("significance"):
                content += f"\n\nSignificance: {entity['significance']}"
            
            if entity.get("associated_entities"):
                content += f"\nAssociated: {entity['associated_entities']}"
            
            return content
        
        else:
            # Generic format
            content = f"{name}"
            if entity.get("description"):
                content += f" - {entity['description']}"
            return content
    
    async def remove_entry(self, character_file: str, entry_id: int) -> bool:
        """Remove an entry from the lorebook"""
        char_data = await self.file_ops.read_json(character_file)
        
        if "data" not in char_data or "character_book" not in char_data["data"]:
            return False
        
        entries = char_data["data"]["character_book"]["entries"]
        
        # Find and remove entry
        for i, entry in enumerate(entries):
            if entry.get("id") == entry_id:
                entries.pop(i)
                await self.file_ops.write_json(character_file, char_data)
                return True
        
        return False
    
    async def get_entry_count(self, character_file: str) -> int:
        """Get number of lorebook entries"""
        try:
            char_data = await self.file_ops.read_json(character_file)
            if "data" in char_data and "character_book" in char_data["data"]:
                return len(char_data["data"]["character_book"]["entries"])
            return 0
        except:
            return 0
    
    # ──────────────────────────────────────────────
    #  Standalone lorebook support (SillyTavern World Info format)
    # ──────────────────────────────────────────────
    
    async def create_standalone_lorebook(self, name: str) -> Dict:
        """Create a new empty standalone lorebook JSON file."""
        from config import config
        
        lorebooks_dir = config.get('sillytavern.lorebooks_dir')
        if not lorebooks_dir:
            raise ValueError("lorebooks_dir not configured in config.yaml")
        
        ldir = Path(lorebooks_dir)
        ldir.mkdir(parents=True, exist_ok=True)
        
        # Sanitize filename
        safe_name = re.sub(r'[^a-zA-Z0-9_\- ]', '', name).strip()
        if not safe_name:
            safe_name = "New_Lorebook"
        
        file_path = ldir / f"{safe_name}.json"
        
        # Don't overwrite existing
        if file_path.exists():
            return {
                "status": "exists",
                "message": f"Lorebook '{safe_name}' already exists",
                "file": str(file_path)
            }
        
        # SillyTavern World Info format
        lorebook_data = {
            "name": name,
            "entries": {}
        }
        
        file_path.write_text(
            json.dumps(lorebook_data, indent=2, ensure_ascii=False),
            encoding='utf-8'
        )
        
        return {
            "status": "created",
            "message": f"Lorebook '{name}' created",
            "file": str(file_path)
        }
    
    async def add_entry_standalone(
        self,
        lorebook_file: str,
        entity: Dict,
        entity_type: str
    ) -> bool:
        """Add an entry to a standalone lorebook (World Info format)."""
        try:
            file_path = Path(lorebook_file)
            data = json.loads(file_path.read_text(encoding='utf-8'))
        except (json.JSONDecodeError, OSError, FileNotFoundError):
            return False
        
        if 'entries' not in data:
            data['entries'] = {}
        
        # Find next available numeric key
        existing_keys = [int(k) for k in data['entries'].keys() if k.isdigit()]
        next_key = str(max(existing_keys) + 1) if existing_keys else "0"
        
        # Check for duplicates by name
        entity_name_lower = entity.get('name', '').lower()
        for key, entry in data['entries'].items():
            keys = entry.get('key', [])
            if any(entity_name_lower == k.lower() for k in keys):
                # Merge instead of duplicate
                old_content = entry.get('content', '')
                new_info = self._format_entity_content(entity, entity_type)
                if new_info not in old_content:
                    entry['content'] = f"{old_content}\n\n[Updated]\n{new_info}"
                
                file_path.write_text(
                    json.dumps(data, indent=2, ensure_ascii=False),
                    encoding='utf-8'
                )
                return True
        
        # Create new entry in World Info format
        entry_id = self._generate_entry_id(entity.get('name', 'Unknown'))
        
        data['entries'][next_key] = {
            "uid": entry_id,
            "key": self._generate_keys(entity.get('name', 'Unknown')),
            "keysecondary": [],
            "comment": f"{entity_type.upper()} - Lorebook Builder",
            "content": self._format_entity_content(entity, entity_type),
            "constant": False,
            "selective": True,
            "selectiveLogic": 0,
            "addMemo": True,
            "order": 100,
            "position": 0,
            "disable": False,
            "excludeRecursion": False,
            "preventRecursion": False,
            "delayUntilRecursion": False,
            "probability": 100,
            "useProbability": True,
            "depth": 4,
            "group": "",
            "groupOverride": False,
            "groupWeight": 100,
            "scanDepth": None,
            "caseSensitive": False,
            "matchWholeWords": None,
            "useGroupScoring": False,
            "automationId": "",
            "role": 0,
            "vectorized": False,
            "sticky": 0,
            "cooldown": 0,
            "delay": 0
        }
        
        file_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding='utf-8'
        )
        return True
    
    def is_standalone_lorebook(self, file_path: str) -> bool:
        """Check if a file is a standalone lorebook (vs character card)."""
        try:
            data = json.loads(Path(file_path).read_text(encoding='utf-8'))
            # Standalone lorebooks have 'entries' at top level, no 'data' key
            return 'entries' in data and 'data' not in data
        except (json.JSONDecodeError, OSError, FileNotFoundError):
            return False
