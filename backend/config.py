import yaml
from pathlib import Path
from typing import Dict, Any

class Config:
    """Configuration manager for STCM"""
    
    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = config_path
        self.data = self.load()
    
    def load(self) -> Dict[str, Any]:
        """Load configuration from YAML file"""
        if not Path(self.config_path).exists():
            raise FileNotFoundError(
                f"Config file not found: {self.config_path}\n"
                "Please copy config.example.yaml to config.yaml and edit it."
            )
        
        with open(self.config_path, 'r') as f:
            return yaml.safe_load(f)
    
    def save(self):
        """Save configuration back to file"""
        with open(self.config_path, 'w') as f:
            yaml.dump(self.data, f, default_flow_style=False)
    
    def get(self, path: str, default=None):
        """
        Get config value using dot notation
        Example: config.get('ollama.url')
        """
        keys = path.split('.')
        value = self.data
        
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key, default)
            else:
                return default
        
        return value
    
    def set(self, path: str, value: Any):
        """
        Set config value using dot notation
        Example: config.set('ollama.model', 'mistral')
        """
        keys = path.split('.')
        data = self.data
        
        for key in keys[:-1]:
            if key not in data:
                data[key] = {}
            data = data[key]
        
        data[keys[-1]] = value
    
    @property
    def ollama_url(self) -> str:
        return self.get('ollama.url', 'http://localhost:11434')
    
    @property
    def ollama_model(self) -> str:
        return self.get('ollama.model', 'llama3.2')
    
    @property
    def ollama_api_key(self) -> str:
        return self.get('ollama.api_key')
    
    @property
    def chats_dir(self) -> str:
        return self.get('sillytavern.chats_dir')
    
    @property
    def characters_dir(self) -> str:
        return self.get('sillytavern.characters_dir')
    
    @property
    def personas_dir(self) -> str:
        return self.get('sillytavern.personas_dir')
    
    @property
    def chat_mappings(self) -> Dict[str, str]:
        return self.get('chat_mappings', {})
    
    @property
    def db_path(self) -> str:
        return self.get('database.path', 'data/stcm.db')

# Global config instance
config = Config()
