import json
from typing import Dict, List, Optional
from pathlib import Path
from services.ollama_client import OllamaClient
from services.lorebook_updater import LorebookUpdater
from database import db

# Entity types supported by the lorebook builder
BUILDER_ENTITY_TYPES = ['npcs', 'factions', 'locations', 'items', 'mythology']

# Map plural keys to singular DB values
BUILDER_TYPE_MAP = {
    'npcs': 'npc',
    'factions': 'faction',
    'locations': 'location',
    'items': 'item',
    'mythology': 'mythology',
}


class LorebookBuilder:
    """
    Build lorebook entries from user-supplied world-building text.
    
    Uses the same Reader AI → Coder AI → Review Queue pipeline
    as the chat scanner, but accepts direct text input instead of
    chat logs.
    """
    
    def __init__(self, ollama_client: OllamaClient):
        self.ollama = ollama_client
        self.updater = LorebookUpdater()
        self._prompts = self._load_prompts()
    
    def _load_prompts(self) -> Dict[str, str]:
        """Load prompt templates from files"""
        prompts = {}
        # Resolve relative to project root (parent of backend/)
        project_root = Path(__file__).resolve().parent.parent.parent
        prompts_dir = project_root / "prompts"
        
        if prompts_dir.exists():
            for prompt_file in prompts_dir.glob("*.txt"):
                prompts[prompt_file.stem] = prompt_file.read_text(encoding='utf-8')
        
        return prompts
    
    # ──────────────────────────────────────────────
    #  Freeform mode: text → Reader AI → entities
    # ──────────────────────────────────────────────
    
    async def process_freeform(
        self,
        text: str,
        lorebook_target: str,
        lorebook_name: str = None
    ) -> Dict:
        """
        Process freeform world-building text.
        
        1. Reader AI extracts entities from raw text
        2. Coder AI formats them as lorebook entries
        3. Entities are added to the review queue
        
        Args:
            text: Raw world-building text from the user
            lorebook_target: Path to target lorebook file
            lorebook_name: Display name (for new lorebooks)
        
        Returns:
            Results dict with entity counts
        """
        print("📖 Lorebook Builder: Extracting entities with READER AI...")
        
        # Extract entities via Reader AI
        entities = await self._extract_entities(text)
        
        total = sum(len(entities.get(t, [])) for t in BUILDER_ENTITY_TYPES)
        print(f"✓ Extraction complete: {total} entities found")
        
        if total == 0:
            return {
                "status": "no_entities",
                "message": "No significant entities found in the text",
                "entities_found": 0
            }
        
        # Add to review queue (LorebookUpdater handles formatting on approval)
        await self._add_to_queue(entities, lorebook_target)
        
        return {
            "status": "success",
            "entities_found": total,
            "lorebook_entries": total,
            "target": lorebook_target,
            "entities": entities
        }
    
    # ──────────────────────────────────────────────
    #  Structured mode: categories → Coder AI
    # ──────────────────────────────────────────────
    
    async def process_structured(
        self,
        categories: Dict[str, str],
        lorebook_target: str,
        lorebook_name: str = None
    ) -> Dict:
        """
        Process structured input (separate text per category).
        
        Each category's text is sent to Reader AI individually,
        then all entities go through the review queue.
        
        Args:
            categories: Dict of category → text (e.g. {"people": "...", "factions": "..."})
            lorebook_target: Path to target lorebook file
            lorebook_name: Display name (for new lorebooks)
        
        Returns:
            Results dict with entity counts
        """
        # Map user-facing category names to entity types
        category_map = {
            'people': 'npcs',
            'factions': 'factions',
            'places': 'locations',
            'items': 'items',
            'mythology': 'mythology',
        }
        
        all_entities = {t: [] for t in BUILDER_ENTITY_TYPES}
        total = 0
        
        for category_name, text in categories.items():
            if not text or not text.strip():
                continue
            
            entity_type = category_map.get(category_name.lower())
            if not entity_type:
                continue
            
            print(f"📖 Processing {category_name}...")
            
            # Extract entities from this category's text
            extracted = await self._extract_entities(text)
            
            # Merge into all_entities
            for etype in BUILDER_ENTITY_TYPES:
                if etype in extracted:
                    all_entities[etype].extend(extracted[etype])
                    total += len(extracted[etype])
        
        if total == 0:
            return {
                "status": "no_entities",
                "message": "No significant entities found in the provided text",
                "entities_found": 0
            }
        
        # Add to review queue (LorebookUpdater handles formatting on approval)
        await self._add_to_queue(all_entities, lorebook_target)
        
        return {
            "status": "success",
            "entities_found": total,
            "lorebook_entries": total,
            "target": lorebook_target,
            "entities": all_entities
        }
    
    # ──────────────────────────────────────────────
    #  Lorebook management
    # ──────────────────────────────────────────────
    
    async def create_lorebook(self, name: str) -> Dict:
        """
        Create a new empty standalone lorebook.
        
        Args:
            name: Display name for the lorebook
        
        Returns:
            Dict with file path and status
        """
        return await self.updater.create_standalone_lorebook(name)
    
    async def list_lorebooks(self) -> List[Dict]:
        """List all available lorebooks (standalone and character-embedded)."""
        from config import config
        
        lorebooks = []
        
        # Standalone lorebooks
        lorebooks_dir = config.get('sillytavern.lorebooks_dir')
        if lorebooks_dir:
            ldir = Path(lorebooks_dir)
            if ldir.exists():
                for f in sorted(ldir.rglob("*.json")):
                    try:
                        data = json.loads(f.read_text(encoding='utf-8'))
                        entry_count = len(data.get('entries', {}))
                        lorebooks.append({
                            "name": data.get('name', f.stem),
                            "file": str(f),
                            "type": "standalone",
                            "entries": entry_count
                        })
                    except (json.JSONDecodeError, OSError):
                        continue
        
        # Character-embedded lorebooks
        chars_dir = config.characters_dir
        if chars_dir:
            cdir = Path(chars_dir)
            if cdir.exists():
                for f in sorted(cdir.rglob("*.json")):
                    try:
                        data = json.loads(f.read_text(encoding='utf-8'))
                        book = data.get('data', {}).get('character_book')
                        if book and book.get('entries'):
                            entries = book['entries']
                            entry_count = len(entries) if isinstance(entries, list) else len(entries.keys())
                            lorebooks.append({
                                "name": f"{f.stem} (Character)",
                                "file": str(f),
                                "type": "character",
                                "entries": entry_count
                            })
                    except (json.JSONDecodeError, OSError):
                        continue
        
        return lorebooks
    
    async def get_lorebook(self, file_path: str) -> Optional[Dict]:
        """Get lorebook contents by file path."""
        try:
            data = json.loads(Path(file_path).read_text(encoding='utf-8'))
            
            # Standalone lorebook
            if 'entries' in data and 'data' not in data:
                return {
                    "name": data.get('name', 'Unknown'),
                    "type": "standalone",
                    "entries": data.get('entries', {}),
                    "entry_count": len(data.get('entries', {}))
                }
            
            # Character-embedded lorebook
            book = data.get('data', {}).get('character_book')
            if book:
                entries = book.get('entries', [])
                return {
                    "name": book.get('name', 'Character Lorebook'),
                    "type": "character",
                    "entries": entries,
                    "entry_count": len(entries) if isinstance(entries, list) else len(entries.keys())
                }
            
            return None
        except (json.JSONDecodeError, OSError, FileNotFoundError):
            return None
    
    # ──────────────────────────────────────────────
    #  Internal methods
    # ──────────────────────────────────────────────
    
    async def _extract_entities(self, text: str) -> Dict:
        """Use Reader AI to extract entities from text."""
        prompt_template = self._prompts.get("lorebook_builder", "")
        if not prompt_template:
            raise ValueError("lorebook_builder.txt prompt not found in prompts/")
        
        prompt = prompt_template.format(input_text=text)
        
        response = await self.ollama.generate_with_reader(prompt, temperature=0.3)
        
        return self._parse_json_response(response)
    
    async def _format_lorebook_entries(self, entities: Dict) -> List[Dict]:
        """Use Coder AI to format entities as lorebook entries."""
        prompt = self._create_formatting_prompt(entities)
        
        response = await self.ollama.generate_with_coder(
            prompt,
            temperature=0.1
        )
        
        try:
            data = json.loads(response)
            return data.get('lorebook_entries', [])
        except json.JSONDecodeError:
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                try:
                    data = json.loads(json_match.group(0))
                    return data.get('lorebook_entries', [])
                except json.JSONDecodeError:
                    pass
            return []
    
    def _create_formatting_prompt(self, entities: Dict) -> str:
        """Create prompt for Coder AI to generate lorebook entries."""
        prompt = """You are a specialized AI for generating SillyTavern lorebook entries.

Given these extracted entities, generate proper lorebook entries in JSON format.

ENTITIES:
"""
        prompt += json.dumps(entities, indent=2)
        
        prompt += """

Generate a JSON object with this structure:
{
  "lorebook_entries": [
    {
      "name": "Entity Name",
      "keys": ["entity name", "variations"],
      "content": "Formatted content for lorebook",
      "type": "npc/faction/location/item/mythology"
    }
  ]
}

RULES:
- Create smart keys (name + variations, nicknames, abbreviations)
- Format content professionally and concisely
- Include relationships, significance, and context
- For mythology entries, include the sub-category (deity, religion, culture, historical event)
- Keep entries concise but informative
- Generate ONLY valid JSON, no markdown

Generate the lorebook entries:"""
        
        return prompt
    
    def _parse_json_response(self, response: str) -> Dict:
        """Extract JSON from LLM response."""
        import re
        
        # Try direct parse
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            pass
        
        # Try code blocks
        json_pattern = r'```(?:json)?\s*(\{.*?\})\s*```'
        matches = re.findall(json_pattern, response, re.DOTALL)
        if matches:
            try:
                return json.loads(matches[0])
            except json.JSONDecodeError:
                pass
        
        # Try any JSON object
        json_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
        matches = re.findall(json_pattern, response, re.DOTALL)
        for match in matches:
            try:
                data = json.loads(match)
                if any(key in data for key in BUILDER_ENTITY_TYPES):
                    return data
            except json.JSONDecodeError:
                continue
        
        # Return empty
        return {t: [] for t in BUILDER_ENTITY_TYPES}
    
    async def _add_to_queue(
        self,
        entities: Dict,
        lorebook_target: str
    ):
        """Add all extracted entities to the review queue."""
        for entity_type, entity_list in entities.items():
            db_type = BUILDER_TYPE_MAP.get(entity_type, entity_type)
            for entity in entity_list:
                await db.add_entity(
                    entity_type=db_type,
                    entity_name=entity.get('name', 'Unknown'),
                    entity_data=entity,
                    target_file=lorebook_target,
                    source_messages="Lorebook Builder (manual input)",
                    confidence_score=entity.get('confidence', 0.8)
                )
