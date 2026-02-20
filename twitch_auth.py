import os
import secrets
import string
import webbrowser
from urllib.parse import urlencode

import requests
from requests.exceptions import RequestException
from dotenv import load_dotenv
import utils.auth_state_manager as auth
from twitch_callback import TwitchCallbackServer
from utils.log_util import get_logger
from utils.config_manager import configs

load_dotenv()
logger = get_logger(__name__)


TWITCH_CLIENT_ID = os.getenv("TWITCH_CLIENT_ID")
TWITCH_CLIENT_SECRET = os.getenv("TWITCH_CLIENT_SECRET")
TWITCH_REDIRECT_URI = os.getenv("TWITCH_REDIRECT_URI")

# Validate critical config at import time so failures are clear
if not TWITCH_CLIENT_ID or not TWITCH_CLIENT_SECRET or not TWITCH_REDIRECT_URI:
  logger.critical("Missing one or more required Twitch environment variables: TWITCH_CLIENT_ID, TWITCH_CLIENT_SECRET, TWITCH_REDIRECT_URI")
  raise RuntimeError("Missing required Twitch environment variables. See README or config.")

def authenticate():
  logger.debug("Starting authorization flow...") 
  is_user_authenticated = False
  while not is_user_authenticated:
    # Check if auth state is valid
    logger.debug("Checking if user authorization is still active...")
    access_token = auth.get_access_token()
    token_validation = validate_access_token(access_token)
    # Refresh if needed
    if token_validation is False:
      logger.debug("Last authorization expired, refreshing...")
      refresh_token = auth.get_refresh_token()
      refreshed = refresh_access_token(refresh_token)
      # If refresh token expired, user needs to login again
      if refreshed is None:
        logger.debug("Refresh expired as well, getting new token...")
        get_user_access_token()

    else:
      is_user_authenticated = True

# TBH I dont even know why but i read that I had to do so
def _generate_state(length: int = 32) -> str:
  alphabet = string.ascii_letters + string.digits
  return "".join(secrets.choice(alphabet) for _ in range(length))

def open_authorization_url(state: str) -> str:
  # Build auth URL for grant flow (URL-encoded)
  base = "https://id.twitch.tv/oauth2/authorize"
  scopes = configs["twitch"].twitch.scopes if configs.get("twitch") and hasattr(configs["twitch"], "twitch") and hasattr(configs["twitch"].twitch, "scopes") else ""
  params = {
    "response_type": "code",
    "client_id": TWITCH_CLIENT_ID,
    "redirect_uri": TWITCH_REDIRECT_URI,
    "state": state,
    "scope": scopes,
  }
  url = f"{base}?{urlencode(params)}"
  logger.debug(f"Opening auth url: {url}")
  webbrowser.open(url)
  return url

# Exchange auth code for access and refresh tokens
def _exchange_code_for_tokens(code: str):
  TOKEN_URL = "https://id.twitch.tv/oauth2/token"
  data = {
    "client_id": TWITCH_CLIENT_ID,
    "client_secret": TWITCH_CLIENT_SECRET,
    "code": code,
    "grant_type": "authorization_code",
    "redirect_uri": TWITCH_REDIRECT_URI,
  }
  try:
    response = requests.post(TOKEN_URL, data=data, timeout=10)
    response.raise_for_status()
    return response.json()
  except RequestException as e:
    logger.error(f"Token exchange failed: {e}")
    return None

# Check if the access token is valid
def validate_access_token(access_token: str):
  logger.info(f"Checking if access token is valid...")
  VALIDATION_URL = "https://id.twitch.tv/oauth2/validate"
  headers = {
    "Authorization": f"OAuth {access_token}"
  }
  try:
    response = requests.get(VALIDATION_URL, headers=headers, timeout=10)
  except RequestException as e:
    logger.error(f"Error checking access token: {e}")
    return False
  # Check for errors
  if response.status_code != 200:
    logger.error(f"Error checking access token: {response.status_code}")
    logger.error(response.text)
    return False
  json_resp = response.json()
  expiration = json_resp.get("expires_in")
  # Checking for min time of expiration (expires soon)
  if expiration < configs["twitch"].twitch.refresh_time_limit:
    logger.warning(f"Token is about to expire, {expiration}s left")
    return False
  logger.info("Access token is valid")
  # Update expiration
  logger.info("Updating expiration...")
  auth.set_expires_in(expiration)
  auth.get_expires_in()
  
  # Set user info
  auth.set_user_id(json_resp.get("user_id"))
  auth.set_user_login(json_resp.get("login"))
  return json_resp

# Refresh access token
def refresh_access_token(refresh_token: str):
  logger.info(f"Refreshing access token...")
  REFRESH_URL = "https://id.twitch.tv/oauth2/token"
  data = {
    "client_id": TWITCH_CLIENT_ID,
    "client_secret": TWITCH_CLIENT_SECRET,
    "grant_type": "refresh_token",
    "refresh_token": refresh_token,
  }
  headers = {
    "Content-Type": "application/x-www-form-urlencoded"
  }
  try:
    response = requests.post(REFRESH_URL, data=data, headers=headers, timeout=10)
  except RequestException as e:
    logger.error(f"Error refreshing access token: {e}")
    return None
  if response.status_code != 200:
    logger.error(f"Error refreshing access token: {response.status_code}")
    logger.error(response.text)
    return None
  logger.info("Access token refreshed")
  json_resp = response.json()
  
  # Save auth state using setters to ensure proper conversion
  auth.set_access_token(json_resp.get("access_token"))
  auth.set_refresh_token(json_resp.get("refresh_token"))
  auth.set_scope(json_resp.get("scope"))
  auth.set_expires_in(json_resp.get("expires_in"))  # This converts to expires_at
  auth.set_token_type(json_resp.get("token_type"))
  
  return json_resp

def get_user_access_token():
  # Start local callback server
  state = _generate_state()
  callback_server = TwitchCallbackServer(expected_state=state)
  callback_server.start()

  # Open browser for user login
  open_authorization_url(state)

  # Wait for authorization code
  try:
    code, error = callback_server.wait_for_code()
  finally:
    callback_server.stop()

  if error:
    raise RuntimeError(f"Twitch authorization failed: {error}")
  if not code:
    raise RuntimeError("Twitch authorization failed: missing authorization code")

  # Exchange code for access/refresh tokens
  token_data = _exchange_code_for_tokens(code)
  
  # Save auth state using setters to ensure proper conversion
  auth.set_access_token(token_data.get("access_token"))
  auth.set_refresh_token(token_data.get("refresh_token"))
  auth.set_scope(token_data.get("scope"))
  auth.set_expires_in(token_data.get("expires_in"))  # This converts to expires_at
  auth.set_token_type(token_data.get("token_type"))


if __name__ == "__main__":
  get_user_access_token()
