import asyncio
import json
from typing import Dict, List
from services.ollama_client import OllamaClient
from services.entity_extractor import EntityExtractor
from services.chunk_processor import ChunkProcessor
from services.chat_reader import ChatReader
from services.hallucination_detector import HallucinationDetector
from database import db

# Map plural entity type keys to singular DB values
ENTITY_TYPE_MAP = {
    'npcs': 'npc',
    'factions': 'faction',
    'locations': 'location',
    'items': 'item',
    'aliases': 'alias',
    'stats': 'stat',
}

class TwoPhaseProcessor:
    """
    Two-phase processing: Reader AI extracts, Coder AI generates updates
    
    Phase 1 (READER AI):
    - Process all chunks
    - Extract entities
    - Merge and deduplicate
    
    Phase 2 (CODER AI):
    - Generate lorebook entries
    - Generate persona updates
    - Batch operations
    """
    
    def __init__(self, ollama_client: OllamaClient):
        self.ollama = ollama_client
    
    async def process_chat(
        self,
        chat_file: str,
        character_file: str,
        force_rescan: bool = False
    ) -> Dict:
        """
        Complete two-phase processing workflow
        
        Returns:
            Results dict with entities found, entries created, etc.
        """
        # Initialize services
        from config import config
        reader = ChatReader(config.chats_dir)
        chunk_processor = ChunkProcessor(reader)
        extractor = EntityExtractor(self.ollama)
        
        # ============================================
        # PHASE 1: READER AI - Extract all entities
        # ============================================
        print("📖 Phase 1: Reading chunks with READER AI...")
        
        # Get chunks
        chunks, metadata = await chunk_processor.get_chunks_to_process(
            chat_file,
            force_rescan
        )
        
        if not chunks:
            return {
                "status": "no_new_messages",
                "message": "No new messages to process",
                "metadata": metadata
            }
        
        # Process all chunks with READER AI
        all_entities = await self._extract_from_all_chunks(chunks, extractor)
        
        # Merge and deduplicate (handles overlap!)
        merged_entities = self._merge_and_deduplicate(all_entities)
        
        total_entities = sum(len(merged_entities[t]) for t in merged_entities.keys())
        
        print(f"✓ Phase 1 complete: {total_entities} unique entities extracted")
        
        # ============================================
        # PHASE 2: CODER AI - Generate updates
        # ============================================
        print("💻 Phase 2: Generating updates with CODER AI...")
        
        # Generate lorebook entries with CODER AI
        lorebook_entries = await self._generate_lorebook_entries(
            merged_entities,
            character_file
        )
        
        # Generate persona updates with CODER AI
        persona_updates = await self._generate_persona_updates(
            merged_entities
        )
        
        print(f"✓ Phase 2 complete: {len(lorebook_entries)} entries generated")
        
        # Add to database queue
        await self._add_to_queue(
            merged_entities,
            character_file,
            metadata
        )
        
        # Update checkpoint
        await chunk_processor.update_checkpoint(
            chat_file,
            metadata['end_index'],
            metadata['total_messages']
        )
        
        return {
            "status": "success",
            "entities_found": total_entities,
            "lorebook_entries": len(lorebook_entries),
            "persona_updates": len(persona_updates),
            "metadata": metadata
        }
    
    async def _extract_from_all_chunks(
        self,
        chunks: List[List[str]],
        extractor: EntityExtractor
    ) -> List[Dict]:
        """
        Phase 1: Extract entities from all chunks using READER AI
        
        Returns list of entity dicts (one per chunk)
        """
        from config import config
        hallucination_detector = HallucinationDetector()
        rate_limit_delay = config.get('ollama.rate_limit_delay', 2)
        batch_size = config.get('ollama.batch_size', 5)
        
        all_chunk_entities = []
        
        for chunk_idx, chunk_texts in enumerate(chunks):
            print(f"  Reading chunk {chunk_idx + 1}/{len(chunks)}...")
            
            try:
                # Use READER AI to extract
                chunk_entities = await extractor.extract_entities(chunk_texts)
                
                # Run hallucination detection
                source_text = "\n".join(chunk_texts)
                chunk_entities = hallucination_detector.filter_hallucinations(
                    chunk_entities, source_text
                )
                
                all_chunk_entities.append(chunk_entities)
                
                # Explicit cleanup
                del source_text
            except Exception as e:
                print(f"  ⚠ Error in chunk {chunk_idx + 1}: {e}")
                continue
            
            # Rate limiting: pause every batch_size chunks
            if (chunk_idx + 1) % batch_size == 0 and chunk_idx + 1 < len(chunks):
                await asyncio.sleep(rate_limit_delay)
        
        return all_chunk_entities
    
    def _merge_and_deduplicate(self, all_chunk_entities: List[Dict]) -> Dict:
        """
        Merge entities from all chunks and handle duplicates from overlaps
        
        This is where overlap deduplication happens!
        """
        merged = {
            'npcs': [],
            'factions': [],
            'locations': [],
            'items': [],
            'aliases': [],
            'stats': []
        }
        
        for chunk_entities in all_chunk_entities:
            for entity_type, entity_list in chunk_entities.items():
                for entity in entity_list:
                    # Check if entity already found
                    existing = self._find_existing_entity(
                        merged.get(entity_type, []),
                        entity
                    )
                    
                    if existing:
                        # MERGE: Combine information from both
                        self._merge_entity_info(existing, entity)
                    else:
                        # NEW: Add to list
                        merged[entity_type].append(entity)
        
        return merged
    
    def _find_existing_entity(self, entity_list: List[Dict], entity: Dict) -> Dict:
        """Find if entity already exists in list (by name)"""
        entity_name = entity.get('name', '').lower().strip()
        
        for existing in entity_list:
            if existing.get('name', '').lower().strip() == entity_name:
                return existing
        
        return None
    
    def _merge_entity_info(self, existing: Dict, new: Dict):
        """
        Merge information from duplicate entities (from overlaps)
        
        Strategy:
        - Take higher confidence
        - Combine descriptions (if different)
        - Increment mention count
        - Preserve all unique information
        """
        # Update confidence (take higher)
        if new.get('confidence', 0) > existing.get('confidence', 0):
            existing['confidence'] = new['confidence']
        
        # Combine descriptions if different
        existing_desc = existing.get('description', '').lower()
        new_desc = new.get('description', '').lower()
        
        if new_desc and new_desc not in existing_desc:
            existing['description'] = f"{existing.get('description', '')} {new.get('description', '')}".strip()
        
        # Add mention counts
        existing['mentions'] = existing.get('mentions', 1) + new.get('mentions', 1)
        
        # Merge other fields (relationship, goals, etc.)
        for key in ['relationship', 'goals', 'leadership', 'territory', 'properties']:
            if key in new and key not in existing:
                existing[key] = new[key]
    
    async def _generate_lorebook_entries(
        self,
        entities: Dict,
        character_file: str
    ) -> List[Dict]:
        """
        Phase 2: Use CODER AI to generate lorebook entries
        
        Sends all entities at once to coder AI for batch generation
        """
        # Prepare prompt for CODER AI
        prompt = self._create_lorebook_generation_prompt(entities)
        
        # Use CODER AI to generate structured lorebook JSON
        response = await self.ollama.generate_with_coder(
            prompt,
            temperature=0.1  # Low temp for structured output
        )
        
        # Parse response
        try:
            entries = json.loads(response)
            return entries.get('lorebook_entries', [])
        except json.JSONDecodeError:
            # Fallback: extract JSON from response
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                entries = json.loads(json_match.group(0))
                return entries.get('lorebook_entries', [])
            return []
    
    def _create_lorebook_generation_prompt(self, entities: Dict) -> str:
        """Create prompt for CODER AI to generate lorebook entries"""
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
      "type": "npc/faction/location/item"
    }
  ]
}

RULES:
- Create smart keys (name + variations)
- Format content professionally
- Include relationships and context
- Keep entries concise but informative
- Generate ONLY valid JSON, no markdown

Generate the lorebook entries:"""
        
        return prompt
    
    async def _generate_persona_updates(self, entities: Dict) -> List[Dict]:
        """
        Phase 2: Use CODER AI to generate persona updates (aliases, stats)
        """
        aliases = entities.get('aliases', [])
        stats = entities.get('stats', [])
        
        if not aliases and not stats:
            return []
        
        # TODO: Implement persona update generation with CODER AI
        print(f"⚠ Persona update generation not yet implemented ({len(aliases)} aliases, {len(stats)} stats skipped)")
        return []
    
    async def _add_to_queue(
        self,
        entities: Dict,
        character_file: str,
        metadata: Dict
    ):
        """Add all entities to review queue"""
        from config import config
        
        char_path = f"{config.characters_dir}/{character_file}"
        source_context = f"Messages {metadata['start_index']}-{metadata['end_index']}"
        
        for entity_type, entity_list in entities.items():
            db_type = ENTITY_TYPE_MAP.get(entity_type, entity_type)
            for entity in entity_list:
                await db.add_entity(
                    entity_type=db_type,
                    entity_name=entity.get('name', 'Unknown'),
                    entity_data=entity,
                    target_file=char_path,
                    source_messages=source_context,
                    confidence_score=entity.get('confidence', 0.5)
                )


# Usage:
# processor = TwoPhaseProcessor(ollama_client)
# result = await processor.process_chat("Jinx.jsonl", "Jinx.json")
