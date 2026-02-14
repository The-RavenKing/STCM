from typing import List, Dict, Tuple
from services.chat_reader import ChatReader
from database import db
from config import config

class ChunkProcessor:
    """
    Process chat messages in overlapping chunks for efficient scanning
    
    Features:
    - Incremental processing (only new messages)
    - Configurable chunk size (adjust for VRAM)
    - Overlapping chunks (preserve context)
    - Checkpoint tracking (resume where left off)
    """
    
    def __init__(self, chat_reader: ChatReader):
        self.reader = chat_reader
        self.chunk_size = config.get('scanning.chunk_size', 20)
        self.overlap = config.get('scanning.chunk_overlap', 5)
        self.max_chunks = config.get('scanning.max_chunks_per_scan', 10)
        self.incremental = config.get('scanning.incremental_mode', True)
    
    async def get_chunks_to_process(
        self,
        chat_file: str,
        force_rescan: bool = False
    ) -> Tuple[List[List[str]], Dict]:
        """
        Get chunks of messages to process
        
        Args:
            chat_file: Chat filename
            force_rescan: Ignore checkpoint and rescan all
        
        Returns:
            (chunks, metadata)
            chunks: List of message lists (each is a chunk)
            metadata: Info about processing (start_index, end_index, etc.)
        """
        # Read all messages
        all_messages = self.reader.read_chat(chat_file)
        total_messages = len(all_messages)
        
        # Get checkpoint
        checkpoint = None
        start_index = 0
        
        if self.incremental and not force_rescan:
            checkpoint = await db.get_checkpoint(chat_file)
            if checkpoint:
                start_index = checkpoint['last_processed_index']
        
        # If nothing new, return empty
        if start_index >= total_messages:
            return [], {
                'total_messages': total_messages,
                'start_index': start_index,
                'end_index': start_index,
                'new_messages': 0,
                'chunks_created': 0
            }
        
        # Get messages to process
        messages_to_process = all_messages[start_index:]
        
        # Create overlapping chunks
        chunks = self._create_overlapping_chunks(messages_to_process)
        
        # Limit chunks per scan
        if len(chunks) > self.max_chunks:
            chunks = chunks[:self.max_chunks]
            end_index = start_index + (self.max_chunks * (self.chunk_size - self.overlap))
        else:
            end_index = total_messages
        
        metadata = {
            'total_messages': total_messages,
            'start_index': start_index,
            'end_index': min(end_index, total_messages),
            'new_messages': len(messages_to_process),
            'chunks_created': len(chunks),
            'had_checkpoint': checkpoint is not None
        }
        
        return chunks, metadata
    
    def _create_overlapping_chunks(self, messages: List[Dict]) -> List[List[str]]:
        """
        Create overlapping chunks from messages
        
        Example with chunk_size=20, overlap=5:
        Chunk 1: messages [0-19]
        Chunk 2: messages [15-34]  (overlaps 15-19)
        Chunk 3: messages [30-49]  (overlaps 30-34)
        
        This preserves context across chunk boundaries.
        """
        if not messages:
            return []
        
        chunks = []
        start = 0
        
        while start < len(messages):
            end = min(start + self.chunk_size, len(messages))
            chunk_messages = messages[start:end]
            
            # Extract text from messages
            chunk_texts = self.reader.extract_text_only(chunk_messages)
            
            chunks.append(chunk_texts)
            
            # Move to next chunk with overlap
            start = start + self.chunk_size - self.overlap
            
            # Break if we've covered all messages
            if end >= len(messages):
                break
        
        return chunks
    
    async def update_checkpoint(
        self,
        chat_file: str,
        processed_up_to: int,
        total_messages: int
    ):
        """Update checkpoint after processing"""
        # Get last message timestamp if available
        messages = self.reader.read_chat(chat_file)
        last_timestamp = None
        
        if processed_up_to < len(messages):
            last_msg = messages[processed_up_to - 1]
            last_timestamp = last_msg.get('date')
        
        await db.update_checkpoint(
            chat_file=chat_file,
            last_processed_index=processed_up_to,
            last_processed_timestamp=last_timestamp,
            total_messages=total_messages
        )
    
    def get_chunk_info(self) -> Dict:
        """Get current chunking configuration"""
        return {
            'chunk_size': self.chunk_size,
            'overlap': self.overlap,
            'max_chunks_per_scan': self.max_chunks,
            'incremental_mode': self.incremental
        }
    
    async def reset_checkpoint(self, chat_file: str):
        """Reset checkpoint to rescan entire chat"""
        await db.reset_checkpoint(chat_file)
    
    def estimate_processing_time(self, num_chunks: int) -> int:
        """
        Estimate processing time in seconds
        
        Args:
            num_chunks: Number of chunks to process
        
        Returns:
            Estimated seconds
        """
        # Rough estimate: ~15 seconds per chunk with Ollama
        return num_chunks * 15


# Example usage:
# chunk_processor = ChunkProcessor(chat_reader)
# chunks, metadata = await chunk_processor.get_chunks_to_process("chat.jsonl")
# for chunk in chunks:
#     entities = await extractor.extract_entities(chunk)
#     # Process entities...
# await chunk_processor.update_checkpoint("chat.jsonl", metadata['end_index'], metadata['total_messages'])
