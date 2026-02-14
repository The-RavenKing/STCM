import aiohttp
import json
from typing import Optional, Tuple, List
from config import config

class OllamaClient:
    """Async client for Ollama API"""
    
    def __init__(
        self,
        base_url: str = None,
        reader_model: str = None,
        coder_model: str = None,
        api_key: str = None,
        timeout: int = 120
    ):
        self.base_url = base_url or config.ollama_url
        self.reader_model = reader_model or config.get('ollama.reader_model', 'llama3.2')
        self.coder_model = coder_model or config.get('ollama.coder_model', 'llama3.2')
        self.api_key = api_key or config.ollama_api_key
        self.timeout = aiohttp.ClientTimeout(total=timeout)
    
    async def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.7,
        model: str = None
    ) -> str:
        """
        Send a prompt to Ollama and get response
        
        Args:
            prompt: The user prompt
            system: Optional system prompt
            temperature: Response randomness (0-1)
            model: Override default model (uses reader_model if not specified)
        
        Returns:
            Generated text response
        """
        # Use specified model or default to reader
        if model is None:
            model = self.reader_model
        
        payload = {
            "model": model,
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
    
    async def generate_with_reader(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.3
    ) -> str:
        """Use reader model for entity extraction"""
        return await self.generate(prompt, system, temperature, model=self.reader_model)
    
    async def generate_with_coder(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.1
    ) -> str:
        """Use coder model for structured file updates"""
        return await self.generate(prompt, system, temperature, model=self.coder_model)
    
    async def test_connection(self) -> Tuple[bool, str]:
        """
        Test if Ollama is accessible and models are available
        
        Returns:
            (success: bool, message: str)
        """
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
                async with session.get(f"{self.base_url}/api/tags") as response:
                    if response.status == 200:
                        data = await response.json()
                        models = [m['name'] for m in data.get('models', [])]
                        
                        reader_ok = self.reader_model in models
                        coder_ok = self.coder_model in models
                        
                        if reader_ok and coder_ok:
                            return True, f"✓ Connected to Ollama. Reader: '{self.reader_model}' ✓, Coder: '{self.coder_model}' ✓"
                        elif reader_ok:
                            return False, f"⚠ Reader model '{self.reader_model}' OK, but coder model '{self.coder_model}' not found. Run: ollama pull {self.coder_model}"
                        elif coder_ok:
                            return False, f"⚠ Coder model '{self.coder_model}' OK, but reader model '{self.reader_model}' not found. Run: ollama pull {self.reader_model}"
                        else:
                            return False, f"✗ Models not installed. Run: ollama pull {self.reader_model} && ollama pull {self.coder_model}"
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
