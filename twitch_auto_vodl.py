import auth_state_manager
from twitch_auth import validate_access_token, refresh_access_token, get_user_access_token
from utils.log_util import get_logger
logger = get_logger(__name__)

def authenticate(): 
  is_user_authenticated = False
  while not is_user_authenticated:
    # Check if auth state is valid
    access_token = auth_state_manager.get_access_token()
    token_validation = validate_access_token(access_token)
    # Refresh if needed
    if token_validation is False:
      refresh_token = auth_state_manager.get_refresh_token()
      refreshed = refresh_access_token(refresh_token)
      # If refresh token expired, user needs to login again
      if refreshed is None:
        get_user_access_token()

    else:
      is_user_authenticated = True

def main():
  logger.info(50*"=")
  authenticate()
  user = auth_state_manager.get_user_login()
  logger.info(f"Successfully authenticated, Hello {user}")
  
    
main()


   

