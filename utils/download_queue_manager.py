import asyncio
from dataclasses import dataclass
from typing import Optional
from utils.log_util import get_logger

logger = get_logger(__name__)


@dataclass
class DownloadTask:
    """Represents a VOD download task queued from a stream end event."""
    stream_id: str
    broadcaster_id: str
    time_of_event: str  # ISO 8601 timestamp when stream ended
    
    def __repr__(self):
        return f"DownloadTask(stream_id={self.stream_id})"


class DownloadQueueManager:
    """Manages a queue of VOD downloads to be processed asynchronously.
    
    This decouples the WebSocket event loop from long-running download operations,
    preventing the WebSocket from becoming unresponsive during downloads.
    """

    def __init__(self, max_concurrent_downloads: int = 1):
        """Initialize the download queue manager.
        
        Args:
            max_concurrent_downloads: Maximum number of concurrent downloads.
                                      Default is 1 (sequential downloads).
        """
        self._queue: asyncio.Queue[DownloadTask] = asyncio.Queue()
        self._max_concurrent = max_concurrent_downloads
        self._active_downloads = 0
        self._lock = asyncio.Lock()
        self._worker_task: Optional[asyncio.Task] = None
        logger.debug(f"DownloadQueueManager initialized (max concurrent: {max_concurrent_downloads})")

    def queue_download(self, task: DownloadTask) -> None:
        """Queue a download task.
        
        This is safe to call from sync or async contexts.
        
        Args:
            task: The DownloadTask to queue.
        """
        try:
            self._queue.put_nowait(task)
            logger.info(f"Queued download: {task}")
        except asyncio.QueueFull:
            logger.error(f"Download queue is full, dropped task: {task}")

    async def process_queue(self, download_handler) -> None:
        """Process queued downloads in the background.
        
        This should be started as an asyncio task and run continuously.
        
        Args:
            download_handler: Async callable that accepts (stream_id, broadcaster_id, time_of_event)
                            and returns True if successful, False otherwise.
        """
        logger.info("Download queue worker starting")
        try:
            while True:
                try:
                    # Get task from queue (blocks until available)
                    task = await asyncio.wait_for(self._queue.get(), timeout=5.0)
                    
                    # Wait if we're at max concurrent
                    while self._active_downloads >= self._max_concurrent:
                        await asyncio.sleep(0.5)
                    
                    # Process the download
                    asyncio.create_task(
                        self._process_single_download(task, download_handler)
                    )
                    
                except asyncio.TimeoutError:
                    # No tasks, just continue
                    continue
                except Exception as e:
                    logger.error(f"Error processing queue: {e}")
                    await asyncio.sleep(1)
                    
        except asyncio.CancelledError:
            logger.info("Download queue worker cancelled")
            # Cancel any remaining tasks
            while not self._queue.empty():
                try:
                    self._queue.get_nowait()
                except asyncio.QueueEmpty:
                    break

    async def _process_single_download(self, task: DownloadTask, download_handler) -> None:
        """Process a single download task.
        
        Args:
            task: The DownloadTask to process.
            download_handler: Async callable to handle the download.
        """
        async with self._lock:
            self._active_downloads += 1
        
        logger.info(f"Starting download for {task}")
        try:
            success = await download_handler(
                stream_id=task.stream_id,
                broadcaster_id=task.broadcaster_id,
                time_of_event=task.time_of_event
            )
            
            if success:
                logger.info(f"Download completed: {task}")
            else:
                logger.warning(f"Download failed: {task}")
                
        except Exception as e:
            logger.error(f"Download error for {task}: {e}")
        finally:
            async with self._lock:
                self._active_downloads -= 1

    def queue_size(self) -> int:
        """Get the current queue size.
        
        Returns:
            Number of tasks waiting in queue.
        """
        return self._queue.qsize()

    def active_downloads(self) -> int:
        """Get the number of currently active downloads.
        
        Returns:
            Number of downloads in progress.
        """
        return self._active_downloads
