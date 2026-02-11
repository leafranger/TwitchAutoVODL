import json
import os
import time
import datetime
from typing import Any, Optional
from utils.log_util import get_logger
from utils.project_definitions import STATE_DIR

logger = get_logger(__name__)

AUTH_STATE_FILE_PATH = os.path.join(STATE_DIR, "auth.json")


def load_auth_state() -> Optional[dict]:
  """Load authentication state from JSON file.
  
  Returns:
    dict: The auth state dictionary, or None if file doesn't exist or is invalid.
  """
  if not os.path.exists(AUTH_STATE_FILE_PATH):
    logger.error(f"Auth state file not found at {AUTH_STATE_FILE_PATH}")
    return None
  
  try:
    with open(AUTH_STATE_FILE_PATH, "r") as f:
      return json.load(f)
  except (json.JSONDecodeError, IOError) as e:
    logger.error(f"Failed to load auth state: {e}")
    return None


def _save_auth_state(auth_state: dict) -> None:
  """Save auth state to file."""
  try:
    with open(AUTH_STATE_FILE_PATH, "w") as f:
      json.dump(auth_state, f)
  except IOError as e:
    logger.error(f"Failed to save auth state: {e}")


def get_info(info_name: str) -> Optional[Any]:
  """Retrieve a value from the auth state.
  
  Args:
    info_name: The key to retrieve from auth state.
    
  Returns:
    The value if found, None otherwise.
  """
  auth_state = load_auth_state()
  
  if auth_state is None:
    logger.error("Auth state is empty or invalid")
    return None

  info = auth_state.get(info_name)
  if info is None:
    logger.warning(f"Auth field '{info_name}' not found")
    return None
  
  logger.debug(f"Retrieved '{info_name}' from auth state")
  return info


def set_info(info_name: str, info: Any) -> bool:
  """Set a value in the auth state.
  
  Args:
    info_name: The key to set in auth state.
    info: The value to set.
    
  Returns:
    True if successful, False otherwise.
  """
  auth_state = load_auth_state()
  
  if auth_state is None:
    logger.error("Cannot set auth field: auth state is empty or invalid")
    return False

  auth_state[info_name] = info
  _save_auth_state(auth_state)
  logger.debug(f"Set '{info_name}' in auth state")
  return True


# ============================================================================
# Concrete getter/setter functions with logging and type hints
# ============================================================================

def get_access_token() -> Optional[str]:
  """Get the access token."""
  logger.debug("Retrieving access token")
  return get_info("access_token")


def set_access_token(access_token: str) -> bool:
  """Set the access token."""
  logger.debug("Setting access token")
  return set_info("access_token", access_token)


def get_refresh_token() -> Optional[str]:
  """Get the refresh token."""
  logger.debug("Retrieving refresh token")
  return get_info("refresh_token")


def set_refresh_token(refresh_token: str) -> bool:
  """Set the refresh token."""
  logger.debug("Setting refresh token")
  return set_info("refresh_token", refresh_token)


def get_expires_in() -> Optional[int]:
  """Get token expiration time in seconds and log expiration details.
  
  Returns:
    The number of seconds until token expires, or None if not available.
  """
  logger.debug("Retrieving token expiration")
  expiration_in_seconds = get_info("expires_in")
  
  if expiration_in_seconds is None:
    logger.warning("Token expiration time not found")
    return None
  
  expiration_unix = int(time.time()) + expiration_in_seconds
  expire_delta = str(datetime.timedelta(seconds=expiration_in_seconds))
  expire_date = datetime.datetime.fromtimestamp(expiration_unix)
  logger.info(f"Token expires in {expire_delta}, at {expire_date} (unix: {expiration_unix})")
  
  return expiration_in_seconds


def set_expires_in(expires_in: int) -> bool:
  """Set token expiration time in seconds."""
  logger.debug("Setting token expiration")
  return set_info("expires_in", expires_in)


def get_scope() -> Optional[str]:
  """Get the token scope."""
  logger.debug("Retrieving token scope")
  return get_info("scope")


def set_scope(scope: str) -> bool:
  """Set the token scope."""
  logger.debug("Setting token scope")
  return set_info("scope", scope)


def get_token_type() -> Optional[str]:
  """Get the token type."""
  logger.debug("Retrieving token type")
  return get_info("token_type")


def set_token_type(token_type: str) -> bool:
  """Set the token type."""
  logger.debug("Setting token type")
  return set_info("token_type", token_type)


def get_user_login() -> Optional[str]:
  """Get the user's login name."""
  logger.debug("Retrieving user login")
  return get_info("login")


def set_user_login(login: str) -> bool:
  """Set the user's login name."""
  logger.debug("Setting user login")
  return set_info("login", login)


def get_user_id() -> Optional[str]:
  """Get the user's ID."""
  logger.debug("Retrieving user ID")
  return get_info("user_id")


def set_user_id(user_id: str) -> bool:
  """Set the user's ID."""
  logger.debug("Setting user ID")
  return set_info("user_id", user_id)


def save_auth_state(auth_state: dict) -> None:
  """Save auth state to file."""
  _save_auth_state(auth_state)


def clear_auth_state() -> None:
  """Clear the auth state file."""
  if os.path.exists(AUTH_STATE_FILE_PATH):
    try:
      os.remove(AUTH_STATE_FILE_PATH)
      logger.info("Auth state cleared")
    except OSError as e:
      logger.error(f"Failed to clear auth state: {e}")


def is_auth_state_expired() -> bool:
  """Check if the auth token is expired.
  
  Returns:
    True if expired or not found, False if still valid.
  """
  expires_in = get_expires_in()
  if expires_in is None:
    logger.warning("Cannot determine expiration: expires_in not found")
    return True
  return time.time() > expires_in