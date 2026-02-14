import json
import re
from typing import Dict, List
from pathlib import Path
from services.ollama_client import OllamaClient

class EntityExtractor:
    """Extract entities from chat messages using LLM"""
    
    def __init__(self, ollama_client: OllamaClient):
        self.ollama = ollama_client
        self.prompts = self._load_prompts()
    
    def _load_prompts(self) -> Dict[str, str]:
        """Load prompt templates from files"""
        prompts = {}
        prompts_dir = Path("prompts")
        
        if prompts_dir.exists():
            for prompt_file in prompts_dir.glob("*.txt"):
                prompt_name = prompt_file.stem
                with open(prompt_file, 'r') as f:
                    prompts[prompt_name] = f.read()
        
        return prompts
    
    async def extract_entities(self, messages: List[str]) -> Dict:
        """
        Extract all entities from chat messages using READER AI
        
        Args:
            messages: List of message strings from chat
        
        Returns:
            Dict with extracted entities by type
        """
        # Combine messages
        chat_text = "\n\n".join(messages)
        
        # Load extraction prompt
        prompt_template = self.prompts.get("entity_extraction", "")
        if not prompt_template:
            raise ValueError("entity_extraction.txt prompt not found")
        
        prompt = prompt_template.format(chat_text=chat_text)
        
        # Get LLM response using READER model
        response = await self.ollama.generate_with_reader(prompt, temperature=0.3)
        
        # Parse JSON response
        entities = self._parse_json_response(response)
        
        # Validate and score
        return self._validate_entities(entities, messages)
    
    def _parse_json_response(self, response: str) -> Dict:
        """Extract JSON from LLM response"""
        # Try direct JSON parse first
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            pass
        
        # Try to find JSON in markdown code blocks
        json_pattern = r'```(?:json)?\s*(\{.*?\})\s*```'
        matches = re.findall(json_pattern, response, re.DOTALL)
        
        if matches:
            try:
                return json.loads(matches[0])
            except json.JSONDecodeError:
                pass
        
        # Try to find any JSON object
        json_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
        matches = re.findall(json_pattern, response, re.DOTALL)
        
        for match in matches:
            try:
                data = json.loads(match)
                # Check if it has expected structure
                if any(key in data for key in ['npcs', 'factions', 'locations', 'items', 'aliases']):
                    return data
            except json.JSONDecodeError:
                continue
        
        # Return empty structure if parsing failed
        return {
            "npcs": [],
            "factions": [],
            "locations": [],
            "items": [],
            "aliases": [],
            "stats": []
        }
    
    def _validate_entities(self, entities: Dict, source_messages: List[str]) -> Dict:
        """
        Validate and enhance entity data
        
        Args:
            entities: Raw extracted entities
            source_messages: Original messages for context
        
        Returns:
            Validated entities with enhanced metadata
        """
        validated = {
            "npcs": [],
            "factions": [],
            "locations": [],
            "items": [],
            "aliases": [],
            "stats": []
        }
        
        # Validate each entity type
        for entity_type in validated.keys():
            if entity_type in entities:
                for entity in entities[entity_type]:
                    # Ensure required fields exist
                    if not entity.get('name'):
                        continue
                    
                    # Set default confidence if not provided
                    if 'confidence' not in entity or entity['confidence'] is None:
                        entity['confidence'] = self._estimate_confidence(entity, source_messages)
                    
                    # Ensure confidence is between 0 and 1
                    entity['confidence'] = max(0.0, min(1.0, entity['confidence']))
                    
                    # Count actual mentions in source
                    if 'mentions' not in entity:
                        entity['mentions'] = self._count_mentions(entity['name'], source_messages)
                    
                    # Add source context if missing
                    if 'source_context' not in entity:
                        entity['source_context'] = self._find_context(entity['name'], source_messages)
                    
                    validated[entity_type].append(entity)
        
        return validated
    
    def _estimate_confidence(self, entity: Dict, messages: List[str]) -> float:
        """Estimate confidence score based on entity details"""
        score = 0.5  # Base score
        
        # Increase for description
        if entity.get('description') and len(entity.get('description', '')) > 20:
            score += 0.2
        
        # Increase for multiple fields filled
        field_count = sum(1 for v in entity.values() if v and str(v).strip())
        score += min(0.2, field_count * 0.05)
        
        # Increase for multiple mentions
        mentions = self._count_mentions(entity['name'], messages)
        score += min(0.1, mentions * 0.03)
        
        return min(1.0, score)
    
    def _count_mentions(self, name: str, messages: List[str]) -> int:
        """Count how many times an entity is mentioned"""
        count = 0
        text = " ".join(messages).lower()
        name_lower = name.lower()
        
        # Count exact matches
        count = text.count(name_lower)
        
        # Count partial matches (first/last name if multiple words)
        if ' ' in name:
            parts = name.split()
            for part in parts:
                if len(part) > 3:  # Only count substantial parts
                    count += text.count(part.lower())
        
        return max(1, count)
    
    def _find_context(self, name: str, messages: List[str], context_chars: int = 100) -> str:
        """Find a snippet of text containing the entity name"""
        name_lower = name.lower()
        
        for message in messages:
            message_lower = message.lower()
            pos = message_lower.find(name_lower)
            
            if pos != -1:
                # Extract context around the name
                start = max(0, pos - context_chars // 2)
                end = min(len(message), pos + len(name) + context_chars // 2)
                
                snippet = message[start:end]
                
                # Add ellipsis if truncated
                if start > 0:
                    snippet = "..." + snippet
                if end < len(message):
                    snippet = snippet + "..."
                
                return snippet
        
        return f"Mentioned: {name}"

# Helper function for easy use
async def extract_from_messages(messages: List[str], ollama_client: OllamaClient = None) -> Dict:
    """
    Convenience function to extract entities from messages
    
    Args:
        messages: List of message strings
        ollama_client: Optional custom Ollama client
    
    Returns:
        Dict of extracted entities
    """
    from services.ollama_client import ollama_client as default_client
    client = ollama_client or default_client
    
    extractor = EntityExtractor(client)
    return await extractor.extract_entities(messages)
