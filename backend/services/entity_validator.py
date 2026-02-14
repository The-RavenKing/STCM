from typing import Dict, List, Tuple
from services.ollama_client import OllamaClient
import json
import re

class EntityValidator:
    """
    Optional validation phase: READER AI reviews extracted entities
    
    Catches:
    - Fuzzy duplicates (Marcus = Marcellous)
    - Relationship conflicts
    - Entity type confusion
    - Low-quality entities
    """
    
    def __init__(self, ollama_client: OllamaClient):
        self.ollama = ollama_client
    
    async def validate_entities(
        self,
        entities: Dict,
        mode: str = "smart"
    ) -> Tuple[Dict, Dict]:
        """
        Validate and clean extracted entities
        
        Args:
            entities: Raw extracted entities from chunks
            mode: "full", "smart", or "conflicts_only"
        
        Returns:
            (validated_entities, validation_report)
        """
        # Determine what needs validation based on mode
        if mode == "conflicts_only":
            needs_validation = self._detect_conflicts(entities)
            if not needs_validation:
                return entities, {"status": "no_conflicts", "changes": []}
        
        elif mode == "smart":
            # Only validate low-confidence or potentially problematic entities
            entities_to_validate = self._filter_needs_validation(entities)
            if not entities_to_validate:
                return entities, {"status": "all_high_confidence", "changes": []}
        
        # Run full LLM validation
        validated, report = await self._run_validation(entities, mode)
        
        return validated, report
    
    def _detect_conflicts(self, entities: Dict) -> bool:
        """Quick check for obvious conflicts"""
        # Check for potential name duplicates
        all_names = []
        for entity_type in entities.values():
            for entity in entity_type:
                name = entity.get('name', '').lower()
                all_names.append(name)
        
        # Check for similar names (fuzzy matching)
        for i, name1 in enumerate(all_names):
            for name2 in all_names[i+1:]:
                if self._names_similar(name1, name2):
                    return True  # Conflict detected!
        
        return False
    
    def _names_similar(self, name1: str, name2: str) -> bool:
        """Check if two names might be the same entity"""
        # Simple similarity checks
        if name1 == name2:
            return True
        
        # One is substring of other
        if name1 in name2 or name2 in name1:
            return True
        
        # First/last name match
        words1 = set(name1.split())
        words2 = set(name2.split())
        if words1 & words2:  # Intersection
            return True
        
        return False
    
    def _filter_needs_validation(self, entities: Dict) -> Dict:
        """Filter entities that need validation (smart mode)"""
        needs_validation = {
            'npcs': [],
            'factions': [],
            'locations': [],
            'items': [],
            'aliases': [],
            'stats': []
        }
        
        for entity_type, entity_list in entities.items():
            for entity in entity_list:
                # Low confidence
                if entity.get('confidence', 1.0) < 0.8:
                    needs_validation[entity_type].append(entity)
                    continue
                
                # Very sparse description
                desc = entity.get('description', '')
                if len(desc) < 20:
                    needs_validation[entity_type].append(entity)
                    continue
                
                # Single mention (might be error)
                if entity.get('mentions', 0) < 2:
                    needs_validation[entity_type].append(entity)
                    continue
        
        return needs_validation
    
    async def _run_validation(
        self,
        entities: Dict,
        mode: str
    ) -> Tuple[Dict, Dict]:
        """
        Run LLM validation on entities
        """
        # Create validation prompt
        prompt = self._create_validation_prompt(entities, mode)
        
        # Use READER AI for validation (same model that extracted)
        response = await self.ollama.generate_with_reader(
            prompt,
            temperature=0.2  # Low temp for consistent validation
        )
        
        # Parse validation response
        validation_result = self._parse_validation_response(response)
        
        # Apply validation fixes
        validated_entities = self._apply_validation(entities, validation_result)
        
        # Create report
        report = {
            "status": "validated",
            "changes": validation_result.get('changes', []),
            "duplicates_merged": validation_result.get('duplicates_merged', 0),
            "entities_removed": validation_result.get('entities_removed', 0),
            "conflicts_resolved": validation_result.get('conflicts_resolved', 0)
        }
        
        return validated_entities, report
    
    def _create_validation_prompt(self, entities: Dict, mode: str) -> str:
        """Create prompt for entity validation"""
        prompt = """You are validating extracted entities from a D&D campaign for quality and consistency.

EXTRACTED ENTITIES:
"""
        prompt += json.dumps(entities, indent=2)
        
        prompt += """

VALIDATION TASKS:
1. FIND DUPLICATES: Identify entities that are the same but named differently
   - "Marcellous" vs "Marcus" (same person?)
   - "The Lieutenant" vs "Marcellous" (title vs name?)
   - "Black Crows" in both NPCs and Factions (type confusion?)

2. RESOLVE CONFLICTS: Check for contradictory information
   - Entity affiliated with multiple factions
   - Conflicting descriptions or roles

3. QUALITY CHECK: Flag low-quality entities
   - Too generic (e.g., "a guard", "some merchant")
   - Insufficient information
   - Single mention with no details

4. RECOMMEND ACTIONS: For each issue found, recommend:
   - MERGE: Combine duplicate entities
   - REMOVE: Delete low-quality entity
   - FLAG: Keep but mark for human review
   - KEEP: Entity is fine

Return ONLY valid JSON with this structure:
{
  "changes": [
    {
      "type": "merge|remove|flag|keep",
      "entity_type": "npc|faction|location|item|alias",
      "entity_name": "Name",
      "reason": "Why this change is needed",
      "merge_with": "Other entity name (if merging)",
      "confidence": 0.9
    }
  ],
  "duplicates_merged": 2,
  "entities_removed": 1,
  "conflicts_resolved": 1
}

Be conservative: Only suggest changes you're confident about (confidence > 0.8).
Generate the validation report:"""
        
        return prompt
    
    def _parse_validation_response(self, response: str) -> Dict:
        """Parse LLM validation response"""
        try:
            # Try direct JSON parse
            return json.loads(response)
        except json.JSONDecodeError:
            # Try to extract JSON from response
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group(0))
                except:
                    pass
        
        # Fallback: no changes
        return {
            "changes": [],
            "duplicates_merged": 0,
            "entities_removed": 0,
            "conflicts_resolved": 0
        }
    
    def _apply_validation(
        self,
        entities: Dict,
        validation_result: Dict
    ) -> Dict:
        """Apply validation changes to entities"""
        validated = entities.copy()
        
        for change in validation_result.get('changes', []):
            change_type = change.get('type')
            entity_type = change.get('entity_type')
            entity_name = change.get('entity_name')
            confidence = change.get('confidence', 0.5)
            
            # Only apply high-confidence changes
            if confidence < 0.8:
                continue
            
            if change_type == 'merge':
                self._merge_entities(
                    validated,
                    entity_type,
                    entity_name,
                    change.get('merge_with')
                )
            
            elif change_type == 'remove':
                self._remove_entity(
                    validated,
                    entity_type,
                    entity_name
                )
            
            elif change_type == 'flag':
                self._flag_entity(
                    validated,
                    entity_type,
                    entity_name,
                    change.get('reason')
                )
        
        return validated
    
    def _merge_entities(
        self,
        entities: Dict,
        entity_type: str,
        name1: str,
        name2: str
    ):
        """Merge two entities"""
        entity_list = entities.get(entity_type, [])
        
        e1 = next((e for e in entity_list if e['name'].lower() == name1.lower()), None)
        e2 = next((e for e in entity_list if e['name'].lower() == name2.lower()), None)
        
        if e1 and e2:
            # Merge e2 into e1
            e1['description'] = f"{e1.get('description', '')} {e2.get('description', '')}".strip()
            e1['mentions'] = e1.get('mentions', 1) + e2.get('mentions', 1)
            e1['confidence'] = max(e1.get('confidence', 0), e2.get('confidence', 0))
            
            # Remove e2
            entity_list.remove(e2)
    
    def _remove_entity(self, entities: Dict, entity_type: str, name: str):
        """Remove low-quality entity"""
        entity_list = entities.get(entity_type, [])
        entities[entity_type] = [
            e for e in entity_list 
            if e['name'].lower() != name.lower()
        ]
    
    def _flag_entity(self, entities: Dict, entity_type: str, name: str, reason: str):
        """Flag entity for human review"""
        entity_list = entities.get(entity_type, [])
        entity = next((e for e in entity_list if e['name'].lower() == name.lower()), None)
        
        if entity:
            entity['flagged'] = True
            entity['flag_reason'] = reason
            entity['confidence'] = min(entity.get('confidence', 1.0), 0.6)  # Lower confidence


# Usage example:
# validator = EntityValidator(ollama_client)
# validated, report = await validator.validate_entities(raw_entities, mode="smart")
# print(f"Merged {report['duplicates_merged']} duplicates")
# print(f"Removed {report['entities_removed']} low-quality entities")
