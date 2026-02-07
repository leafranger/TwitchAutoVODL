import json
import os
import time
from utils.log_util import get_logger
import datetime
from utils.project_definitions import STATE_DIR
logger = get_logger(__name__)

AUTH_STATE_FILE_PATH = os.path.join(STATE_DIR, "auth.json")

def get_info(info_name:str):
  auth_state = load_auth_state()
  
  if auth_state is None:
    logger.error("Auth state is empty")
    return

  info = auth_state.get(info_name)
  if info is None:
    logger.error(f"{info_name} not found")
    return
  logger.debug(f"Got {info}")
  return info
def set_info(info_name, info):
  auth_state = load_auth_state()
  
  if auth_state is None:
    logger.error("Auth state is empty")
    return

  auth_state[info_name] = info
  with open(AUTH_STATE_FILE_PATH, "w") as f:
    logger.debug(f"Setting {info_name} to {info}")
    json.dump(auth_state, f)

def load_auth_state():
  if not os.path.exists(AUTH_STATE_FILE_PATH):
    logger.error("Auth state file not found")
    return None
  with open(AUTH_STATE_FILE_PATH, "r") as f:
    return json.load(f)

# access token
def get_access_token():
  logger.info("Retriveing access token...")
  return get_info("access_token")
def set_access_token(access_token: str):
  logger.info("Setting access token...")
  set_info("access_token", access_token)

# refresh token
def get_refresh_token():
  logger.info("Retrieving access token...")
  return get_info("refresh_token")
def set_refresh_token(refresh_token: str):
  logger.info("Setting refresh token...")
  set_info("refresh_token", refresh_token)

# expires at
def get_expires_in():
  logger.info("Getting token expiration...")
  expiration_in_seconds = get_info("expires_in")
  expiration_unix = int(time.time()) + expiration_in_seconds
  expire_delta = str(datetime.timedelta(seconds=expiration_in_seconds))
  date = datetime.datetime.fromtimestamp(expiration_unix)
  logger.info(f"Token expires in {str(expire_delta)}, {date} | [{expiration_unix}]")
  return expiration_in_seconds
def set_expires_in(expires_in: int):
  logger.info("Setting token expiration...")
  set_info("expires_in", expires_in)

# scope
def get_scope():
  logger.info("Retrieving scopes...")
  return get_info("scope")
def set_scope(scope: str):
  logger.info("Setting scopes...")
  set_info("scope", scope)

# token type
def get_token_type():
  logger.info("Getting token type...")
  return get_info("token_type")
def set_token_type(token_type: str):
  logger.info("Getting token type...")
  set_info("token_type", token_type)

# user login
def get_user_login():
  logger.info("Getting user's name...")
  return get_info("login")
def set_user_login(login:str):
  logger.info("Setting user's name...")
  set_info("login", login)

# user id
def get_user_id():
  logger.info("Getting user id...")
  return get_info("user_id")
def set_user_id(user_id:str):
  logger.info("Setting user id...")
  set_info("user_id", user_id)

# Save auth state to file
def save_auth_state(auth_state: dict):
  with open(AUTH_STATE_FILE_PATH, "w") as f:
    json.dump(auth_state, f)

def clear_auth_state():
  if os.path.exists(AUTH_STATE_FILE_PATH):
    os.remove(AUTH_STATE_FILE_PATH)

# Check if auth state is expired
def is_auth_state_expired():
  expires_in = get_expires_in()
  if expires_in is None:
    return True
  return time.time() > expires_in