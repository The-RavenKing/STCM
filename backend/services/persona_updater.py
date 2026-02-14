from typing import Dict
from utils.file_ops import FileOperations
from database import db
import re

class PersonaUpdater:
    """Update persona files with new aliases and stats"""
    
    def __init__(self):
        self.file_ops = FileOperations()
    
    async def add_alias(
        self,
        persona_file: str,
        alias_data: Dict
    ) -> bool:
        """
        Add new alias/identity to persona
        
        Args:
            persona_file: Path to persona JSON file
            alias_data: Alias information (name, purpose, appearance, etc.)
        
        Returns:
            Success boolean
        """
        # Load persona
        persona = await self.file_ops.read_json(persona_file)
        
        # Get default persona key (with fallback for files without default_persona)
        persona_key = persona.get("default_persona")
        if not persona_key:
            # Fall back to first available key in persona_descriptions
            persona_descs = persona.get("persona_descriptions", {})
            if persona_descs:
                persona_key = list(persona_descs.keys())[0]
            else:
                print("Error: No persona descriptions found")
                return False
        
        # Get persona description
        persona_desc = persona["persona_descriptions"].get(persona_key, {})
        description = persona_desc.get("description", "")
        
        # Parse existing identities section
        identities_pattern = r'=== CRITICAL: SECRET IDENTITIES? ===.*?(?==== |\Z)'
        identities_match = re.search(identities_pattern, description, re.DOTALL)
        
        if identities_match:
            # Extract existing identities
            identities_section = identities_match.group(0)
            identity_count = len(re.findall(r'\d+\.\s+\*\*', identities_section))
            
            # Create new alias entry
            new_number = identity_count + 1
            new_alias = f"\n{new_number}. **{alias_data['name']}** ({alias_data.get('purpose', 'Disguise')}): {alias_data.get('appearance', 'Appearance varies')}. {alias_data.get('description', '')}"
            
            # Insert before the next section
            updated_section = identities_section.replace(
                '\n\n=== ',
                f'{new_alias}\n\n=== '
            )
            
            # Replace in full description
            description = description.replace(identities_section, updated_section)
        else:
            # No identities section exists, create one
            new_section = f"""
=== CRITICAL: SECRET IDENTITIES ===
1. **{alias_data['name']}** ({alias_data.get('purpose', 'Disguise')}): {alias_data.get('appearance', 'Created using Disguise Self')}. {alias_data.get('description', '')}

"""
            # Insert after first section
            description = re.sub(
                r'(===.*?===.*?\n)',
                r'\1' + new_section,
                description,
                count=1
            )
        
        # Update persona
        persona["persona_descriptions"][persona_key]["description"] = description
        
        # Save
        await self.file_ops.write_json(persona_file, persona)
        
        return True
    
    async def update_stat(
        self,
        persona_file: str,
        stat_data: Dict
    ) -> bool:
        """
        Update character stats in persona
        
        Args:
            persona_file: Path to persona JSON
            stat_data: Stat change info (stat_name, new_value, etc.)
        
        Returns:
            Success boolean
        """
        # Load persona
        persona = await self.file_ops.read_json(persona_file)
        
        # Get default persona key (with fallback)
        persona_key = persona.get("default_persona")
        if not persona_key:
            persona_descs = persona.get("persona_descriptions", {})
            if persona_descs:
                persona_key = list(persona_descs.keys())[0]
            else:
                return False
        
        description = persona["persona_descriptions"][persona_key]["description"]
        
        stat_name = stat_data.get('stat_name', '')
        new_value = stat_data.get('new_value', '')
        
        # Update specific stats
        if 'HP' in stat_name.upper() or 'HEALTH' in stat_name.upper():
            # Update HP value
            description = re.sub(
                r'Hit Points:\s*\d+',
                f'Hit Points: {new_value}',
                description
            )
        elif 'GOLD' in stat_name.upper() or 'GP' in stat_name.upper():
            # Update gold value
            description = re.sub(
                r'Gold:\s*[\d,]+\s*GP',
                f'Gold: {new_value} GP',
                description
            )
        elif 'LEVEL' in stat_name.upper():
            # Update level (more complex - might need proficiency bonus, etc.)
            description = re.sub(
                r'level\s+\d+',
                f'level {new_value}',
                description,
                flags=re.IGNORECASE
            )
        
        # Save
        persona["persona_descriptions"][persona_key]["description"] = description
        await self.file_ops.write_json(persona_file, persona)
        
        return True
    
    async def add_equipment(
        self,
        persona_file: str,
        item_name: str,
        item_description: str = None
    ) -> bool:
        """
        Add equipment to persona
        
        Args:
            persona_file: Path to persona JSON
            item_name: Name of item
            item_description: Optional description
        
        Returns:
            Success boolean
        """
        persona = await self.file_ops.read_json(persona_file)
        
        persona_key = persona.get("default_persona")
        if not persona_key:
            return False
        
        description = persona["persona_descriptions"][persona_key]["description"]
        
        # Find equipment section
        equipment_pattern = r'(=== EQUIPMENT & GEAR ===.*?Carrying:)(.*?)(?=Weight Carried:)'
        match = re.search(equipment_pattern, description, re.DOTALL)
        
        if match:
            equipment_list = match.group(2)
            
            # Add new item
            if item_description:
                new_item = f", {item_name} ({item_description})"
            else:
                new_item = f", {item_name}"
            
            # Insert before the end
            equipment_list = equipment_list.rstrip() + new_item
            
            description = description.replace(
                match.group(2),
                equipment_list
            )
            
            persona["persona_descriptions"][persona_key]["description"] = description
            await self.file_ops.write_json(persona_file, persona)
            
            return True
        
        return False
