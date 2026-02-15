import yaml
from pathlib import Path
from typing import Dict, Any

class Config:
    """Configuration manager for STCM"""
    
    def __init__(self, config_path: str = "config.yaml"):
        # Resolve relative to project root (parent of backend/)
        self.project_root = Path(__file__).resolve().parent.parent
        self.config_path = str(self.project_root / config_path)
        self.data = self.load()
    
    def load(self) -> Dict[str, Any]:
        """Load configuration from YAML file, creating from template if missing"""
        config_file = Path(self.config_path)
        
        if not config_file.exists():
            # Auto-create from example template so the server can boot
            example = self.project_root / "config.example.yaml"
            if example.exists():
                import shutil
                shutil.copy(str(example), str(config_file))
                print("✓ Created config.yaml from template (first run)")
            else:
                raise FileNotFoundError(
                    f"Neither config.yaml nor config.example.yaml found in {self.project_root}"
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
    def lorebooks_dir(self) -> str:
        return self.get('sillytavern.lorebooks_dir')
    
    @property
    def chat_mappings(self) -> Dict[str, str]:
        return self.get('chat_mappings', {})
    
    @property
    def db_path(self) -> str:
        return self.get('database.path', 'data/stcm.db')

    @property
    def needs_setup(self) -> bool:
        """Check if essential configuration is still missing or has placeholder values."""
        chats = self.chats_dir or ''
        chars = self.characters_dir or ''
        # Unset or still contains the example placeholder path
        return (
            not chats or '/path/to/' in chats
            or not chars or '/path/to/' in chars
        )

# Global config instance
config = Config()
