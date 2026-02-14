import os
import time
from pathlib import Path
from typing import Optional
from contextlib import contextmanager

# Cross-platform file locking
if os.name == 'nt':
    # Windows
    import msvcrt

    def _lock_file(fd, exclusive=True, blocking=True):
        """Acquire a lock on the file descriptor (Windows)."""
        mode = msvcrt.LK_NBLCK if not blocking else msvcrt.LK_LOCK
        if not exclusive and not blocking:
            mode = msvcrt.LK_NBRLCK
        elif not exclusive:
            mode = msvcrt.LK_RLCK
        # Lock 1 byte — standard convention for advisory file locking on Windows.
        # All STCM code uses size=1 consistently so locks are interoperable.
        msvcrt.locking(fd, mode, 1)

    def _unlock_file(fd):
        """Release a lock on the file descriptor (Windows)."""
        try:
            msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
        except OSError:
            pass
else:
    # POSIX (Linux, macOS)
    import fcntl

    def _lock_file(fd, exclusive=True, blocking=True):
        """Acquire a lock on the file descriptor (POSIX)."""
        if exclusive:
            flag = fcntl.LOCK_EX
        else:
            flag = fcntl.LOCK_SH
        if not blocking:
            flag |= fcntl.LOCK_NB
        fcntl.flock(fd, flag)

    def _unlock_file(fd):
        """Release a lock on the file descriptor (POSIX)."""
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        except OSError:
            pass


class FileLockManager:
    """
    Prevent concurrent access to character/persona files
    
    Ensures STCM doesn't corrupt files while SillyTavern is using them.
    Cross-platform: uses msvcrt on Windows, fcntl on POSIX.
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
        lock_path = path.with_suffix('.lock')
        
        try:
            # Create lock file
            lock_file = open(lock_path, 'w')
            
            # Try to acquire lock with timeout
            start_time = time.time()
            exclusive = (mode == 'exclusive')
            
            while True:
                try:
                    _lock_file(lock_file.fileno(), exclusive=exclusive, blocking=False)
                    break
                except (IOError, OSError):
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
                    _unlock_file(lock_file.fileno())
                    lock_file.close()
                    if lock_path.exists():
                        lock_path.unlink()
                except Exception:
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
            _lock_file(lock_file.fileno(), exclusive=True, blocking=False)
            _unlock_file(lock_file.fileno())
            lock_file.close()
            if lock_path.exists():
                lock_path.unlink()
            return True
        except (IOError, OSError):
            return False
    
    def is_file_in_use(self, file_path: str) -> bool:
        """Check if file is currently locked"""
        return not self.try_lock(file_path)


# Usage in lorebook_updater.py:
# with file_lock_manager.lock_file(character_file):
#     data = read_json(character_file)
#     # ... modify data ...
#     write_json(character_file, data)
