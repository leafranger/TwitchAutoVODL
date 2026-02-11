import json
import asyncio
import websockets
import aiohttp
from utils.log_util import get_logger
from utils.config_manager import configs
from utils.download_queue_manager import DownloadQueueManager, DownloadTask
from twitch_vod_download import download_latest_video_async, Streams
from twitch_auth import authenticate

logger = get_logger(__name__)



#\LOCAL WS
EVENTSUB_WS_URL = f"ws://127.0.0.1:8080/ws?keepalive_timeout_seconds={configs['twitch'].websocket.keepalive_timeout_seconds}"
EVENTSUB_API_URL = "http://localhost:8080/eventsub/subscriptions"

# Real Websocket addresses
EVENTSUB_WS_URL  = f"wss://eventsub.wss.twitch.tv/ws?keepalive_timeout_seconds={configs['twitch'].websocket.keepalive_timeout_seconds}"
EVENTSUB_API_URL =  "https://api.twitch.tv/helix/eventsub/subscriptions"

class TwitchEventSubWebSocket:
  def __init__(self, token, client_id, broadcaster_id):
    self.token = token
    self.client_id = client_id
    self.broadcaster_id = broadcaster_id
    # Client states
    self.session_id = None
    self.ws = None
    self.reconnect_task = None
    self.reconnecting = False
    # Download queue
    self.download_queue = DownloadQueueManager(max_concurrent_downloads=1)
    self.queue_worker_task = None
    # Stream state manager (use shared singleton imported from twitch_vod_download)
    self.stream_manager = Streams

  async def start_connection(self):
    # Get max concurrent downloads from config
    max_concurrent = configs["twitch"].vod_download.download_threads
    self.download_queue = DownloadQueueManager(max_concurrent_downloads=max_concurrent)
    
    # Start the background download queue worker
    self.queue_worker_task = asyncio.create_task(
        self.download_queue.process_queue(self._download_handler)
    )
    logger.info(f"Started download queue worker (max concurrent: {max_concurrent})")
    
    backoff = 1
    while True:
      try:
        await self._connect()
        backoff = 1
      except Exception as e:
        logger.error(f"WebSocket crashed: {e}")
      logger.warning(f"Reconnecting in {backoff} seconds")
      await asyncio.sleep(backoff)
      backoff = min(backoff *2, 30)

  async def _connect(self):
    try:
      async with websockets.connect(EVENTSUB_WS_URL) as ws:
        self.ws = ws
        logger.info("Connecting to EventSub WebSocket")
        async for message in ws:
          try:
            data = json.loads(message)
            await self._handle_message(data)
          except json.JSONDecodeError:
            logger.error("Received invalid JSON from Twitch")
          except Exception as e:
            logger.error("Unexpected error while handling message")
            logger.error(e)
    except websockets.exceptions.ConnectionClosedError as e:
      logger.error(f"WebSocket connection closed unexpectedly: {e}")

    except Exception as e:
      logger.error(f"Failed to connect to EventSub WebSocket: {e}")

  async def _handle_message(self, data):
    metadata = data.get("metadata", {})
    msg_type = metadata.get("message_type")

    logger.debug(f"Received message type: {msg_type}")
    match msg_type:
      case "session_welcome"    : await self._on_session_welcome(data)
      case "notification"       : await self._on_notification(data)
      case "session_keepalive"  : await self._on_keepalive(data)
      case "session_reconnect"  : await self._on_reconnect(data)
      case "revocation"         : await self._on_revocation(data)
      # Default
      case _ :logger.warning(f"Unknown message type: {msg_type}")

  async def _register_subscription(self, event_type: str):
    headers = {
      "Client-ID": self.client_id,
      "Authorization": f"Bearer {self.token}",
      "Content-Type": "application/json"
    }

    body = {
      "type": event_type,
      "version": "1",
      "condition": {
          "broadcaster_user_id": self.broadcaster_id
      },
      "transport": {
          "method": "websocket",
          "session_id": self.session_id
      }
    }

    try:
      async with aiohttp.ClientSession() as session:
        async with session.post(EVENTSUB_API_URL, headers=headers, json=body) as resp:
          result = await resp.json()

          if resp.status == 202:
            logger.info(f"Subscription created: {event_type}")
          elif resp.status == 401:
            logger.warning("Unauthorized access (token probably expired)")
            authenticate()
          else:
            logger.error(
              f"Failed to create subscription {event_type} "
              f"(status {resp.status}): {result}"
            )

    except Exception as e:
      logger.error(f"Error registering subscription {event_type}: {e}")
  
  async def _on_session_welcome(self, data):
    logger.info("Received welcome message")
    session = data["payload"]["session"]
    logger.info(
      f"Session ID: {session["id"]} {session["status"]} at {session["connected_at"]}. Keepalive for {session["keepalive_timeout_seconds"]} seconds"
    )
    self.session_id = session["id"]
    await self._register_subscription("stream.online")
    await self._register_subscription("stream.offline")

  async def _on_keepalive(self, data):
    metadata = data["metadata"]
    logger.debug(f"[{metadata["message_id"]}] {metadata["message_type"]} at {metadata["message_timestamp"]}")

  async def _on_revocation(self, data):
    metadata = data["metadata"]
    subscription = data["payload"]["subscription"]
    logger.debug(f"[{metadata["message_id"]}] {metadata["message_type"]} at {metadata["message_timestamp"]}")
    logger.error(f"[ID: {subscription["id"]}] Subscription revoked. Status: {subscription["status"]} of {subscription["type"]}")

  async def _on_reconnect(self, data):
    if self.reconnecting:
      return # Already reconnecting
    self.reconnecting = True  
    metadata = data["metadata"]
    logger.debug(f"[{metadata["message_id"]}] {metadata["message_type"]} at {metadata["message_timestamp"]}")
    logger.warning("Websocket needs to reconnect...")
    
    session = data["payload"]["session"]
    new_url = session["reconnect_url"]

    # Parallel connection
    self.reconnect_task = asyncio.create_task(self._connect_new_socket(new_url))

  async def _on_notification(self, data):
    metadata = data["metadata"]
    subscription = data["payload"]["subscription"]
    event = data["payload"]["event"]
    event_type = subscription["type"]
    logger.debug(f"[{metadata["message_id"]}] {metadata["message_type"]} at {metadata["message_timestamp"]}")

    logger.debug(f"Event received: {event_type}")
    logger.debug(json.dumps(event, indent=2))

    if event_type == "stream.offline":
      logger.info("Received stream.offline message")
      await self._on_stream_end(
          username      = event["broadcaster_user_name"],
          time_of_event = metadata["message_timestamp"]
        )

    if event_type == "stream.online":
      logger.info("Received stream.online message")
      await self._on_stream_start(
        username   = event["broadcaster_user_name"],
        stream_id  = event["id"],
        start_time = event["started_at"],
        type = event["type"]
      )
  
  async def _on_stream_start(self, username, stream_id, start_time, type):
    """Handle stream.online event.
    
    Args:
      username: The broadcaster's username.
      stream_id: The unique stream ID.
      start_time: ISO 8601 timestamp of stream start.
      type: The stream type (live, playlist, watch_party, premiere, rerun).
    """
    # Check if stream type is allowed
    allowed_stream_types: list[str] = configs["twitch"].twitch.allowed_stream_types
    logger.debug(f"Allowed stream types: {allowed_stream_types}")
    
    if type not in allowed_stream_types:
      logger.warning(
        f"Stream started is type '{type}', not in allowed types {allowed_stream_types}. Ignoring."
      )
      return

    logger.info(f"Stream started: {username} [{stream_id}] at {start_time}")
    
    # Save to stream state manager
    self.stream_manager.add_stream(
      stream_id,
      {
        "created_at": start_time,
        "status": "pending",
        "username": username,
        "type": type
      }
    )
    logger.info(f"Tracking stream {stream_id} for download when it ends")

  async def _on_stream_end(self, username, time_of_event):
    """Handle stream.offline event.
    
    This event doesn't include the stream ID, so we queue all pending streams
    (streams that haven't been downloaded or started downloading yet).
    
    Args:
      username: The broadcaster's username.
      time_of_event: ISO 8601 timestamp of when stream ended.
    """
    logger.info(f"Stream offline event received for {username} at {time_of_event}")
    
    # Find all pending streams that haven't been downloaded or started downloading
    all_streams = self.stream_manager.list_streams()
    pending_streams = [
      (sid, info) for sid, info in all_streams.items()
      if info.get("status") == "pending"
    ]
    
    if not pending_streams:
      logger.warning("No pending streams found to download")
      return
    
    logger.info(f"Found {len(pending_streams)} pending stream(s) to queue for download")
    
    # Queue all pending streams
    for stream_id, stream_info in pending_streams:
      task = DownloadTask(
        stream_id=stream_id,
        broadcaster_id=self.broadcaster_id,
        time_of_event=time_of_event
      )
      self.download_queue.queue_download(task)
      logger.info(f"Queued download for stream {stream_id}, queue size: {self.download_queue.queue_size()}")

  async def _connect_new_socket(self, url):
    try:
      async with websockets.connect(url) as new_ws:
        logger.info("Reconnecting to new WebSocket...")

        async for message in new_ws:
          data = json.loads(message)
          msg_type = data["metadata"]["message_type"]

          if msg_type == "session_welcome":
            logger.info("New connection received welcome. Switching sockets")

            # Closing old socket
            await self.ws.close()
            self.ws = new_ws
            self.reconnecting = False
            return
        await self._handle_message(data)
    except Exception as e:
      logger.error(f"Reconnect socket failed: {e}")
      self.reconnecting = False

  async def _download_handler(self, stream_id: str, broadcaster_id: str, time_of_event: str) -> bool:
    """Handle a single download task from the queue.
    
    Args:
      stream_id: The stream ID to download.
      broadcaster_id: The broadcaster's ID.
      time_of_event: ISO 8601 timestamp of stream end.
      
    Returns:
      True if download successful, False otherwise.
    """
    logger.info(f"Download handler processing stream {stream_id}")
    try:
      # Call the async download function
      success = await download_latest_video_async(time_of_event, broadcaster_id, stream_id)
      return success
    except Exception as e:
      logger.error(f"Download handler exception for stream {stream_id}: {e}")
      return False
