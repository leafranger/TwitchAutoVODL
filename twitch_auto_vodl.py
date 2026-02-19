import asyncio
import utils.auth_state_manager as auth
from twitch_auth import TWITCH_CLIENT_ID, authenticate
from utils.log_util import get_logger
from twitch_websocket import TwitchEventSubWebSocket
from utils.token_refresh_monitor import start_token_refresh_monitor, stop_token_refresh_monitor
import twitch_vod_download

logger = get_logger(__name__)

def main():
  authenticate()
  user = auth.get_user_login()
  logger.info(f"Successfully authenticated, Hello {user}")
  
  # Start automatic token refresh monitor
  logger.info("Starting automatic token refresh monitor...")
  start_token_refresh_monitor(check_interval=30)
  
  logger.info("Starting EventSub WebSocket connection...")
  logger.info("Waiting for stream events. Downloads will be queued automatically.")

  try:
    client = TwitchEventSubWebSocket(
      token = auth.get_access_token(),
      broadcaster_id = auth.get_user_id(),
      client_id=TWITCH_CLIENT_ID
    )
    asyncio.run(client.start_connection())
  finally:
    # Stop the monitor when the application exits
    logger.info("Shutting down token refresh monitor...")
    stop_token_refresh_monitor()

if __name__ == "__main__":
  main()