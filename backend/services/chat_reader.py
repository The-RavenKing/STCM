import json
from typing import List, Dict, Optional
from pathlib import Path
from datetime import datetime

class ChatReader:
    """Read and parse SillyTavern chat logs (.jsonl format)"""
    
    def __init__(self, chats_dir: str):
        self.chats_dir = Path(chats_dir)
    
    def list_chat_files(self) -> List[str]:
        """List all .jsonl chat files in the directory"""
        if not self.chats_dir.exists():
            return []
        
        return [str(f.relative_to(self.chats_dir)) for f in self.chats_dir.rglob("*.jsonl")]
    
    def read_chat(self, chat_file: str, last_n: int = None) -> List[Dict]:
        """
        Read a chat log file
        
        Args:
            chat_file: Name of the chat file
            last_n: Optional - only return last N messages
        
        Returns:
            List of message dictionaries
        """
        chat_path = self.chats_dir / chat_file
        
        if not chat_path.exists():
            raise FileNotFoundError(f"Chat file not found: {chat_path}")
        
        messages = []
        
        with open(chat_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                
                try:
                    data = json.loads(line)
                    
                    # Skip metadata line (first line)
                    if 'chat_metadata' in data:
                        continue
                    
                    # Extract message data
                    message = {
                        'name': data.get('name', 'Unknown'),
                        'is_user': data.get('is_user', False),
                        'text': data.get('mes', ''),
                        'date': data.get('send_date', ''),
                        'swipes': data.get('swipes', []),
                        'extra': data.get('extra', {})
                    }
                    
                    messages.append(message)
                    
                except json.JSONDecodeError as e:
                    print(f"Warning: Failed to parse line {line_num} in {chat_file}: {e}")
                    continue
        
        # Return last N messages if specified
        if last_n and last_n > 0:
            return messages[-last_n:]
        
        return messages
    
    def get_messages_since(
        self,
        chat_file: str,
        since_date: datetime
    ) -> List[Dict]:
        """
        Get messages since a specific date
        
        Args:
            chat_file: Name of the chat file
            since_date: Only return messages after this date
        
        Returns:
            List of message dictionaries
        """
        all_messages = self.read_chat(chat_file)
        
        filtered = []
        for msg in all_messages:
            msg_date_str = msg.get('date', '')
            if not msg_date_str:
                continue
            
            try:
                # Parse ISO format date
                msg_date = datetime.fromisoformat(msg_date_str.replace('Z', '+00:00'))
                
                if msg_date > since_date:
                    filtered.append(msg)
            except ValueError:
                # Skip if date parsing fails
                continue
        
        return filtered
    
    def extract_text_only(self, messages: List[Dict]) -> List[str]:
        """
        Extract just the text content from messages
        
        Args:
            messages: List of message dictionaries
        
        Returns:
            List of text strings
        """
        texts = []
        
        for msg in messages:
            # Skip system messages
            if msg.get('is_system', False):
                continue
            
            # Get the message text
            text = msg.get('text', '').strip()
            
            if text:
                # Prepend speaker name for context
                speaker = msg.get('name', 'Unknown')
                texts.append(f"{speaker}: {text}")
        
        return texts
    
    def get_character_from_chat(self, chat_file: str) -> Optional[str]:
        """
        Try to determine which character this chat is with
        
        Args:
            chat_file: Name of the chat file (may include subdirectory path)
        
        Returns:
            Character name or None
        """
        # Chat files are typically named: CharacterName_-_date.jsonl
        # or CharacterName.jsonl
        # With recursive scanning, chat_file may be "subdir/CharacterName_-_date.jsonl"
        
        # Extract just the filename (ignore subdirectory)
        base_name = Path(chat_file).stem
        
        # Try to extract character name from filename
        if '_-_' in base_name:
            char_name = base_name.split('_-_')[0]
        elif '-' in base_name:
            char_name = base_name.split('-')[0]
        else:
            char_name = base_name
        
        return char_name.strip()
    
    def get_message_count(self, chat_file: str) -> int:
        """Get total number of messages in a chat"""
        chat_path = self.chats_dir / chat_file
        
        if not chat_path.exists():
            return 0
        
        count = 0
        with open(chat_path, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip() and 'chat_metadata' not in line:
                    count += 1
        
        return count
    
    def get_chat_info(self, chat_file: str) -> Dict:
        """
        Get summary information about a chat
        
        Returns:
            Dict with chat metadata
        """
        messages = self.read_chat(chat_file)
        
        if not messages:
            return {
                'file': chat_file,
                'message_count': 0,
                'character': self.get_character_from_chat(chat_file),
                'last_message_date': None
            }
        
        # Get date range
        dates = [msg['date'] for msg in messages if msg.get('date')]
        
        return {
            'file': chat_file,
            'message_count': len(messages),
            'character': self.get_character_from_chat(chat_file),
            'first_message_date': dates[0] if dates else None,
            'last_message_date': dates[-1] if dates else None,
            'participants': list(set(msg['name'] for msg in messages if msg.get('name')))
        }
