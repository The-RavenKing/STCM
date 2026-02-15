import json
import logging
from typing import Dict, Any, Optional
from services.ollama_client import OllamaClient

logger = logging.getLogger(__name__)

class CharacterBuilder:
    """
    Service for generating and modifying SillyTavern characters (DMs/Personas).
    """

    def __init__(self, ollama_client: OllamaClient):
        self.ollama_client = ollama_client

    async def generate_character(self, description: str) -> Dict[str, Any]:
        """
        Generate a new character profile from a description.
        """
        system_prompt = """You are an expert character creator for roleplay games. 
Your task is to create a detailed character profile based on the user's description.
Output MUST be valid JSON only, matching the SillyTavern card format.
Do not include markdown formatting or explanations.

Required JSON Structure:
{
    "name": "Character Name",
    "description": "Detailed physical and personality description...",
    "personality": "Concise personality traits...",
    "scenario": "Context or setting for the character...",
    "first_mes": "An engaging opening message from the character...",
    "mes_example": "Example dialogue (User: ... Character: ...)..."
}
"""
        user_prompt = f"Create a character based on this description:\n\n{description}"

        try:
            response = await self.ollama_client.generate_with_coder(
                prompt=user_prompt,
                system=system_prompt,
                temperature=0.7 
            )
            
            # Clean response to ensure valid JSON
            cleaned_response = self._clean_json_response(response)
            character_data = json.loads(cleaned_response)
            
            # Ensure critical fields exist
            required_fields = ["name", "description", "first_mes"]
            for field in required_fields:
                if field not in character_data:
                    character_data[field] = "To be defined..."
            
            return character_data

        except json.JSONDecodeError:
            logger.error(f"Failed to decode JSON from Ollama response: {response}")
            raise ValueError("Ollama failed to generate valid JSON format.")
        except Exception as e:
            logger.error(f"Error generating character: {e}")
            raise

    async def summarize_character(self, character_data: Dict[str, Any]) -> str:
        """
        Generate a summary of an existing character for context.
        """
        description = character_data.get("description", "")
        personality = character_data.get("personality", "")
        first_mes = character_data.get("first_mes", "")
        
        prompt = f"""Summarize this character's concept, personality, and role in 2-3 sentences.
        
        Description: {description}
        Personality: {personality}
        First Message: {first_mes}
        """
        
        try:
            summary = await self.ollama_client.generate_with_reader(prompt=prompt)
            return summary.strip()
        except Exception as e:
            logger.error(f"Error summarizing character: {e}")
            return "Could not generate summary."

    async def modify_character(self, character_data: Dict[str, Any], instructions: str) -> Dict[str, Any]:
        """
        Modify specific fields of a character based on instructions.
        """
        system_prompt = """You are an expert character editor. 
Your task is to modify the provided character JSON based on the user's instructions.
Only modify fields that are relevant to the instructions. Keep other fields unchanged.
Output MUST be valid JSON only.
"""
        user_prompt = f"""Character Data:
{json.dumps(character_data, indent=2)}

Instructions:
{instructions}

Return the updated JSON.
"""
        try:
            response = await self.ollama_client.generate_with_coder(
                prompt=user_prompt,
                system=system_prompt,
                temperature=0.7
            )
            
            cleaned_response = self._clean_json_response(response)
            return json.loads(cleaned_response)

        except Exception as e:
            logger.error(f"Error modifying character: {e}")
            raise

    def _clean_json_response(self, response: str) -> str:
        """Helper to extract JSON from potential markdown blocks"""
        response = response.strip()
        if response.startswith("```json"):
            response = response[7:]
        if response.startswith("```"):
            response = response[3:]
        if response.endswith("```"):
            response = response[:-3]
        return response.strip()
