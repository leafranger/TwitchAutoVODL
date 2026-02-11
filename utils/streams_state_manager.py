import threading
from typing import Any, Dict, Optional
from utils.log_util import get_logger

logger = get_logger(__name__)


class StreamStateManager:
    """Thread-safe manager for tracking active stream state.
    
    Maintains a dictionary of stream information with automatic locking
    to ensure thread-safe operations across async contexts.
    """

    def __init__(self):
        """Initialize the stream state manager."""
        self._state: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    def add_stream(self, stream_id: str, info: Dict[str, Any]) -> None:
        """Add a new stream to tracking.
        
        Args:
            stream_id: Unique identifier for the stream.
            info: Dictionary of stream metadata.
        """
        logger.debug(f"Adding stream [{stream_id}]")
        with self._lock:
            self._state[stream_id] = info.copy()

    def get_stream(self, stream_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve stream information by ID.
        
        Args:
            stream_id: Unique identifier for the stream.
            
        Returns:
            Stream info dict if found, None otherwise.
        """
        with self._lock:
            stream_info = self._state.get(stream_id)
            if stream_info:
                logger.debug(f"Retrieved stream [{stream_id}]")
            return stream_info

    def update_stream(self, stream_id: str, key: str, value: Any) -> bool:
        """Update a specific field in a stream's info.
        
        Args:
            stream_id: Unique identifier for the stream.
            key: The field name to update.
            value: The new value for the field.
            
        Returns:
            True if update successful, False if stream not found.
        """
        logger.debug(f"Updating stream [{stream_id}]: {key} = {value}")
        with self._lock:
            if stream_id in self._state:
                self._state[stream_id][key] = value
                return True
            
            logger.warning(f"Cannot update stream [{stream_id}]: stream not found")
            return False

    def pop_stream(self, stream_id: str) -> Optional[Dict[str, Any]]:
        """Remove and retrieve stream information.
        
        Args:
            stream_id: Unique identifier for the stream.
            
        Returns:
            Stream info dict if found, None otherwise.
        """
        logger.debug(f"Removing stream [{stream_id}]")
        with self._lock:
            return self._state.pop(stream_id, None)

    def has_stream(self, stream_id: str) -> bool:
        """Check if a stream is being tracked.
        
        Args:
            stream_id: Unique identifier for the stream.
            
        Returns:
            True if stream exists, False otherwise.
        """
        with self._lock:
            return stream_id in self._state

    def list_streams(self) -> Dict[str, Dict[str, Any]]:
        """Get a snapshot of all tracked streams.
        
        Returns:
            Dictionary mapping stream IDs to their info.
        """
        with self._lock:
            return dict(self._state)

    def stream_count(self) -> int:
        """Get the number of currently tracked streams.
        
        Returns:
            Number of active streams.
        """
        with self._lock:
            return len(self._state)

    def clear_all_streams(self) -> int:
        """Clear all tracked streams.
        
        Returns:
            Number of streams that were cleared.
        """
        with self._lock:
            count = len(self._state)
            self._state.clear()
            logger.info(f"Cleared {count} streams")
            return count
