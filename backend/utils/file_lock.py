import fcntl
import time
from pathlib import Path
from typing import Optional
from contextlib import contextmanager

class FileLockManager:
    """
    Prevent concurrent access to character/persona files
    
    Ensures STCM doesn't corrupt files while SillyTavern is using them
    """
    
    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.locks = {}
    
    @contextmanager
    def lock_file(self, file_path: str, mode: str = 'exclusive'):
        """
        Context manager for file locking
        
        Usage:
            with lock_manager.lock_file('character.json'):
                # Safe to read/write
                data = read_file()
                write_file(data)
        """
        path = Path(file_path)
        lock_file = None
        
        try:
            # Create lock file
            lock_path = path.with_suffix('.lock')
            lock_file = open(lock_path, 'w')
            
            # Try to acquire lock with timeout
            start_time = time.time()
            while True:
                try:
                    if mode == 'exclusive':
                        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    else:
                        fcntl.flock(lock_file.fileno(), fcntl.LOCK_SH | fcntl.LOCK_NB)
                    break
                except IOError:
                    # Lock is held by another process
                    if time.time() - start_time > self.timeout:
                        raise TimeoutError(
                            f"Could not acquire lock for {file_path} after {self.timeout}s. "
                            f"SillyTavern may be using this file."
                        )
                    time.sleep(0.1)
            
            yield
            
        finally:
            # Release lock
            if lock_file:
                try:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
                    lock_file.close()
                    lock_path.unlink()
                except:
                    pass
    
    def try_lock(self, file_path: str) -> bool:
        """
        Try to acquire lock without blocking
        
        Returns True if lock acquired, False if file is in use
        """
        path = Path(file_path)
        lock_path = path.with_suffix('.lock')
        
        try:
            lock_file = open(lock_path, 'w')
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            lock_file.close()
            lock_path.unlink()
            return True
        except IOError:
            return False
    
    def is_file_in_use(self, file_path: str) -> bool:
        """Check if file is currently locked"""
        return not self.try_lock(file_path)


# Usage in lorebook_updater.py:
# with file_lock_manager.lock_file(character_file):
#     data = read_json(character_file)
#     # ... modify data ...
#     write_json(character_file, data)
