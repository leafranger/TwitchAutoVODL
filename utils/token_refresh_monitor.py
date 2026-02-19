"""
Token Refresh Monitor

Monitors the token expiration time and automatically refreshes it
before it expires, based on the configured refresh_time_limit.
"""
import time
import threading
from typing import Optional
from utils.log_util import get_logger
from utils.config_manager import configs
import utils.auth_state_manager as auth

logger = get_logger(__name__)


class TokenRefreshMonitor:
  """Background monitor that automatically refreshes the access token before expiration."""
  
  def __init__(self, check_interval: int = 30):
    """
    Initialize the token refresh monitor.
    
    Args:
      check_interval: How often to check token expiration (in seconds). Default: 30
    """
    self.check_interval = check_interval
    self._stop_event = threading.Event()
    self._thread: Optional[threading.Thread] = None
    self._refresh_callback = None
    
    # Get refresh time limit from config
    self.refresh_time_limit = configs["twitch"].twitch.refresh_time_limit
    logger.info(f"Token refresh monitor initialized with {self.refresh_time_limit}s threshold")
  
  def set_refresh_callback(self, callback):
    """
    Set a callback function to be called when token needs refresh.
    The callback should handle the actual token refresh logic.
    
    Args:
      callback: Function to call for refreshing the token. Should return True on success.
    """
    self._refresh_callback = callback
    logger.debug("Refresh callback registered")
  
  def _monitor_loop(self):
    """Main monitoring loop that runs in the background thread."""
    logger.info("Token refresh monitor started")
    
    while not self._stop_event.is_set():
      try:
        # Get current token expiration time
        expires_in = auth.get_expires_in()
        
        if expires_in is None:
          logger.warning("Cannot determine token expiration time, skipping check")
          self._stop_event.wait(self.check_interval)
          continue

        # Sleep until we are within the refresh window
        seconds_until_check = expires_in - self.refresh_time_limit
        if seconds_until_check > 0:
          logger.debug(
            f"Token is still valid ({expires_in}s remaining). "
            f"Next check in {seconds_until_check}s"
          )
          self._stop_event.wait(seconds_until_check)
          continue

        logger.warning(
          f"Token is expiring soon ({expires_in}s left, threshold: {self.refresh_time_limit}s). "
          "Attempting automatic refresh..."
        )
        
        # Execute refresh
        success = self._execute_refresh()
        
        if success:
          logger.info("Token refreshed successfully by monitor")
        else:
          logger.error("Failed to refresh token automatically")
      
      except Exception as e:
        logger.error(f"Error in token refresh monitor loop: {e}", exc_info=True)
      
      # Short wait to avoid tight loops after refresh or error
      self._stop_event.wait(self.check_interval)
    
    logger.info("Token refresh monitor stopped")
  
  def _execute_refresh(self) -> bool:
    """
    Execute the token refresh operation.
    
    Returns:
      True if refresh was successful, False otherwise.
    """
    try:
      if self._refresh_callback:
        return self._refresh_callback()
      else:
        # Default refresh logic using auth manager
        return self._default_refresh()
    except Exception as e:
      logger.error(f"Exception during token refresh: {e}", exc_info=True)
      return False
  
  def _default_refresh(self) -> bool:
    """
    Default token refresh implementation.
    
    Returns:
      True if refresh was successful, False otherwise.
    """
    # Import here to avoid circular dependency
    from twitch_auth import refresh_access_token
    
    refresh_token = auth.get_refresh_token()
    if not refresh_token:
      logger.error("Cannot refresh: refresh token not found")
      return False
    
    result = refresh_access_token(refresh_token)
    return result is not None
  
  def start(self):
    """Start the background monitoring thread."""
    if self._thread and self._thread.is_alive():
      logger.warning("Token refresh monitor is already running")
      return
    
    self._stop_event.clear()
    self._thread = threading.Thread(target=self._monitor_loop, daemon=True, name="TokenRefreshMonitor")
    self._thread.start()
    logger.info("Token refresh monitor thread started")
  
  def stop(self):
    """Stop the background monitoring thread."""
    if not self._thread or not self._thread.is_alive():
      logger.warning("Token refresh monitor is not running")
      return
    
    logger.info("Stopping token refresh monitor...")
    self._stop_event.set()
    self._thread.join(timeout=5)
    
    if self._thread.is_alive():
      logger.warning("Token refresh monitor thread did not stop gracefully")
    else:
      logger.info("Token refresh monitor stopped successfully")
  
  def is_running(self) -> bool:
    """Check if the monitor is currently running."""
    return self._thread is not None and self._thread.is_alive()


# Global monitor instance
_monitor_instance: Optional[TokenRefreshMonitor] = None


def start_token_refresh_monitor(check_interval: int = 30) -> TokenRefreshMonitor:
  """
  Start the global token refresh monitor.
  
  Args:
    check_interval: How often to check token expiration (in seconds). Default: 30
    
  Returns:
    The monitor instance.
  """
  global _monitor_instance
  
  if _monitor_instance and _monitor_instance.is_running():
    logger.warning("Token refresh monitor is already running")
    return _monitor_instance
  
  _monitor_instance = TokenRefreshMonitor(check_interval=check_interval)
  _monitor_instance.start()
  return _monitor_instance


def stop_token_refresh_monitor():
  """Stop the global token refresh monitor."""
  global _monitor_instance
  
  if _monitor_instance:
    _monitor_instance.stop()
    _monitor_instance = None


def get_monitor_instance() -> Optional[TokenRefreshMonitor]:
  """Get the current monitor instance (if any)."""
  return _monitor_instance
