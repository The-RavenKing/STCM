import aiohttp
import json
from typing import Optional, Tuple, List
from config import config

class OllamaClient:
    """Async client for Ollama API"""
    
    def __init__(
        self,
        base_url: str = None,
        model: str = None,
        api_key: str = None,
        timeout: int = 120
    ):
        self.base_url = base_url or config.ollama_url
        self.model = model or config.ollama_model
        self.api_key = api_key or config.ollama_api_key
        self.timeout = aiohttp.ClientTimeout(total=timeout)
    
    async def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.7
    ) -> str:
        """
        Send a prompt to Ollama and get response
        
        Args:
            prompt: The user prompt
            system: Optional system prompt
            temperature: Response randomness (0-1)
        
        Returns:
            Generated text response
        """
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature
            }
        }
        
        if system:
            payload["system"] = system
        
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        
        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            async with session.post(
                f"{self.base_url}/api/generate",
                json=payload,
                headers=headers
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"Ollama API error: {response.status} - {error_text}")
                
                result = await response.json()
                return result.get("response", "")
    
    async def test_connection(self) -> Tuple[bool, str]:
        """
        Test if Ollama is accessible
        
        Returns:
            (success: bool, message: str)
        """
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
                async with session.get(f"{self.base_url}/api/tags") as response:
                    if response.status == 200:
                        data = await response.json()
                        models = [m['name'] for m in data.get('models', [])]
                        
                        if self.model in models:
                            return True, f"✓ Connected to Ollama. Model '{self.model}' is available."
                        else:
                            return False, f"⚠ Ollama is running, but model '{self.model}' is not installed. Available: {', '.join(models)}"
                    else:
                        return False, f"✗ Ollama responded with status {response.status}"
        except aiohttp.ClientError as e:
            return False, f"✗ Cannot connect to Ollama at {self.base_url}: {str(e)}"
        except Exception as e:
            return False, f"✗ Error testing Ollama connection: {str(e)}"
    
    async def list_models(self) -> List[str]:
        """Get list of available models"""
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
                async with session.get(f"{self.base_url}/api/tags") as response:
                    if response.status == 200:
                        data = await response.json()
                        return [m['name'] for m in data.get('models', [])]
                    return []
        except:
            return []

# Global Ollama client instance
ollama_client = OllamaClient()
