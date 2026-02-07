import asyncio
import utils.auth_state_manager as auth
from twitch_auth import TWITCH_CLIENT_ID, authenticate
from utils.log_util import get_logger
from twitch_websocket import TwitchEventSubWebSocket
import twitch_vod_download
logger = get_logger(__name__)

def main():
  authenticate()
  user = auth.get_user_login()
  logger.info(f"Successfully authenticated, Hello {user}")
  
  # twitch_vod_download.download_latest_video("2026-02-03T04:01:11Z", auth.get_user_id())

  client = TwitchEventSubWebSocket(
    token = auth.get_access_token(),
    broadcaster_id = auth.get_user_id(),
    client_id=TWITCH_CLIENT_ID
  )
  asyncio.run(client.start_connection())
  
  
    
main()