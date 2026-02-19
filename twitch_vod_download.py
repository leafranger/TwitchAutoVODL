import ast
import os
import re
import subprocess
import time
import requests
from utils.log_util import get_logger
from utils.timestamps_converters import parse_iso_z
logger = get_logger(__name__)
from utils.config_manager import configs
import utils.auth_state_manager as auth
from twitch_auth import TWITCH_CLIENT_ID, refresh_access_token
from utils.streams_state_manager import StreamStateManager
from utils.project_definitions import TWITCH_DL_CLI_DIR, FFMPEG_PATH_DIR, VODS_DIR

Streams = StreamStateManager()

def _ensure_token_valid():
  """Check if access token is expired and refresh if needed.
  
  Returns:
    True if token is valid after check/refresh, False if refresh failed.
  """
  if auth.is_auth_state_expired():
    logger.warning("Access token has expired, attempting refresh...")
    refresh_token = auth.get_refresh_token()
    if not refresh_token:
      logger.error("Cannot refresh: refresh token not found")
      return False
    
    result = refresh_access_token(refresh_token)
    if result is None:
      logger.error("Failed to refresh access token")
      return False
    
    logger.info("Token refreshed successfully")
    return True
  
  return True

def save_latest_stream_info(stream_info):
  Streams.add_stream(
    stream_info["stream_id"],
    {
      "created_at" : stream_info["created_at"],
      "status"     : "pending"
    }
  )

def get_user_videos(broadcaster_id):
  """Get the latest videos for a broadcaster.
  
  Args:
    broadcaster_id: The broadcaster's user ID.
  
  Returns:
    List of video data dicts from Twitch API, or None if error.
  """
  # Ensure token is still valid before making API call
  if not _ensure_token_valid():
    logger.error("Cannot proceed: access token is expired and refresh failed")
    return None
  
  n_of_videos = configs["twitch"].vod_download.latest_vods_amount
  logger.debug(f"Fetching users latest {n_of_videos} videos")
  TWITCH_USER_VODS_URL = (
  f"https://api.twitch.tv/helix/videos"
  f"?user_id={broadcaster_id}"
  f"&type=archive"
  f"&first={n_of_videos}"
  )
  headers = {
    "Authorization": f"Bearer {auth.get_access_token()}",
    "Client-Id": f"{TWITCH_CLIENT_ID}"
  }
  try:
    response = requests.get(TWITCH_USER_VODS_URL, headers=headers, timeout=10)
    videos = response.json().get("data", [])
    
    if videos:
      logger.debug(f"API returned {len(videos)} videos - checking stream_id match:")
      for v in videos:
        logger.debug(
          f"  video_id={v.get('id')}, stream_id={v.get('stream_id')}, "
          f"type={v.get('type')}, viewable={v.get('viewable')}"
        )
    
    return videos
  except Exception as e:
    logger.error(f"Error getting videos for [{broadcaster_id}]: {e}")
    return None

# Given the latest videos, check which are available
def check_if_videos_published(broadcaster_id, target_stream_id=None):
  """Check if videos are published for tracked streams.
  
  Args:
    broadcaster_id: The broadcaster's user ID.
    target_stream_id: Optional - check only this specific stream_id.
                     If None, checks all tracked streams.
  
  Returns:
    True if at least one valid video was found and video_id was set, False otherwise.
  """
  logger.debug("Checking if videos are published...")
  
  # Log what streams we're tracking
  tracked_streams = list(Streams.list_streams().keys())
  logger.debug(f"Currently tracking stream_ids: {tracked_streams}")
  
  videos_data = get_user_videos(broadcaster_id)
  if not videos_data:
    logger.warning("No videos returned from API")
    return False

  logger.debug(f"API returned {len(videos_data)} videos")
  is_stream_ready_for_download = False

  for video in videos_data:
    stream_id = video.get("stream_id")
    video_id = video.get("id")
    
    logger.debug(
      f"Checking video {video_id}: stream_id={stream_id}, "
      f"type={video.get('type')}, viewable={video.get('viewable')}, "
      f"published_at={video.get('published_at')}"
    )
    
    # Skip if this stream isn't tracked, or if we're looking for a specific stream and this isn't it
    if not Streams.has_stream(stream_id):
      logger.debug(f"  → Video stream_id {stream_id} not in tracked streams {tracked_streams}")
      continue
    if target_stream_id and stream_id != target_stream_id:
      logger.debug(f"  → Video stream_id {stream_id} doesn't match target {target_stream_id}")
      continue
    
    # Stream is tracked, now check if video is valid for download
    if video["type"] != "archive":
      logger.debug(f"  → FAIL: Video type is '{video['type']}', not 'archive'")
      continue
    if video["viewable"] != "public":
      logger.debug(f"  → FAIL: Video not public (viewable={video['viewable']})")
      continue
    if video["published_at"] is None:
      logger.debug(f"  → FAIL: Video not yet published (published_at is None)")
      continue
    
    # All checks passed, this video is ready
    logger.info(f"✓ Video {video_id} ready for download (stream {stream_id})")
    is_stream_ready_for_download = True
    Streams.update_stream(stream_id, "video_id", video["id"])
    
    # If looking for specific stream, we can return now
    if target_stream_id:
      break
      
  return is_stream_ready_for_download

def is_video_downloadable(broadcaster_id, target_stream_id=None):
  """Check if a video is available for download (with retries).
  
  Args:
    broadcaster_id: The broadcaster's user ID.
    target_stream_id: Optional - check only this specific stream_id.
  
  Returns:
    True if video is ready for download, False if not available within retry limit.
  """
  cfg = configs["twitch"].vod_download
  max_retries = cfg.fetch_max_retries
  cooldown = cfg.fetch_retry_cooldown

  for retry in range(max_retries):
    logger.debug(f"Attempt #{retry+1}/{max_retries}...")
    is_video_available = check_if_videos_published(broadcaster_id, target_stream_id)
    if is_video_available:
      logger.debug("Video available for download, proceeding...")
      return True
    else:
      if retry < max_retries - 1:
        logger.debug(f"Video not ready, retrying in {cooldown}s... (attempt {retry+1}/{max_retries})")
        time.sleep(cooldown)
  
  logger.warning(
    f"Video not available for download after {max_retries} attempts "
    f"({max_retries * cooldown}s total wait)"
  )
  return False

def download_latest_video(time_of_event, broadcaster_id, stream_id=None):
  """Download the latest video for a stream.
  
  Args:
    time_of_event: ISO 8601 timestamp of when stream ended.
    broadcaster_id: The broadcaster's user ID.
    stream_id: Specific stream_id to download. If provided, will wait for this stream's video
              to be published before downloading. If None, will download first available pending stream.
  
  Returns:
    True if download completed successfully, False if video not available or download failed.
  """
  if not is_video_downloadable(broadcaster_id, stream_id):
    logger.error(f"Video not downloadable for stream {stream_id}")
    return False

  # If stream_id provided, download only that one
  if stream_id:
    if not Streams.has_stream(stream_id):
      logger.error(f"Stream {stream_id} not found in state manager")
      return False
    
    stream_info = Streams.get_stream(stream_id)
    if not stream_info:
      logger.error(f"Cannot retrieve info for stream {stream_id}")
      return False
    
    video_id = stream_info.get("video_id")
    if not video_id:
      logger.error(f"No video_id found for stream {stream_id}")
      return False
    
    return _download_single_stream(stream_id, stream_info, time_of_event, video_id)
  
  # Otherwise download all pending streams
  streams = Streams.list_streams()
  pending_streams = [(sid, info) for sid, info in streams.items() if info.get("status") == "pending"]
  
  if not pending_streams:
    logger.warning("No pending streams found to download")
    return False
  
  all_successful = True
  for stream_id, stream_info in pending_streams:
    video_id = stream_info.get("video_id")
    if not video_id:
      logger.warning(f"No video_id for stream {stream_id}, skipping")
      all_successful = False
      continue
    
    success = _download_single_stream(stream_id, stream_info, time_of_event, video_id)
    all_successful = all_successful and success
  
  return all_successful


def _download_single_stream(stream_id: str, stream_info: dict, time_of_event: str, video_id: str) -> bool:
  """Download a single stream's video, chat, and chat render.
  
  STREAM_ID vs VIDEO_ID:
    stream_id: Used for state tracking (which streams handled)
    video_id: Used for downloading (TwitchDownloader --id parameter)
  
  Args:
    stream_id: The stream ID being downloaded.
    stream_info: The stream info dict.
    time_of_event: ISO 8601 timestamp of when stream ended.
    video_id: The video ID to download.
  
  Returns:
    True if all downloads succeeded, False otherwise.
  """
  broadcaster = auth.get_user_login()
  parsed_time = parse_iso_z(time_of_event).strftime("%Y%m%d%H%M%S")
  filename = f"{broadcaster}_{parsed_time}_{video_id}"
  
  logger.info(f"Download stream_id={stream_id} (tracking) video_id={video_id} (download)")
  Streams.update_stream(stream_id, "status", "downloading")
  
  # Download video
  success = download_video(video_id, filename)
  if not success:
    logger.error(f"Failed to download video for stream {stream_id}")
    Streams.update_stream(stream_id, "status", "failed")
    return False
  
  # Download chat
  success = download_chat(video_id, filename)
  if not success:
    logger.error(f"Failed to download chat for stream {stream_id}")
    Streams.update_stream(stream_id, "status", "failed")
    return False
  
  # Render chat
  success = download_chat_as_render(filename)
  if not success:
    logger.error(f"Failed to render chat for stream {stream_id}")
    Streams.update_stream(stream_id, "status", "failed")
    return False
  
  logger.info(f"Stream {stream_id} download completed successfully")
  Streams.update_stream(stream_id, "status", "done")
  return True

# Remember to use video_id and not stream_id
def download_video(
  video_id: str,
  filename: str,
):
  """Download VOD video file.
  
  Args:
    video_id: The Twitch video ID (used for --id parameter).
    filename: Output filename base.
  """
  cfg = configs["twitch"].vod_download
  cmd = [
    os.path.join(TWITCH_DL_CLI_DIR, "TwitchDownloaderCLI.exe"),
    "videodownload",
    "--id", str(video_id),
    "--output", os.path.join(VODS_DIR, filename, f"{filename}_vod.{cfg.vods.download_format}"),
    "--quality", cfg.vods.download_quality,
    "--threads", str(cfg.download_threads),
    "--bandwidth", str(cfg.max_thread_bandwidth),
    "--ffmpeg-path", os.path.join(FFMPEG_PATH_DIR, "ffmpeg.exe"),
    "--collision", "Rename"
  ]
  logger.debug("Running cmd: " + " ".join(
    f'"{str(c)}"' if " " in str(c) else str(c)
    for c in cmd
  ))

  logger.info(f"Starting download of Video @ {filename}")

  start_time = time.time()

  try:
    process = subprocess.Popen(
      cmd,
      cwd=TWITCH_DL_CLI_DIR,
      stdout=subprocess.PIPE,
      stderr=subprocess.PIPE,
      text = True,
      bufsize= 1
    )
  
    for raw in process.stdout:
      line = raw.strip()
      if not line: 
        continue
      if line.startswith("[") and line.endswith("]") and "'" in line:
        try:
          parsed = ast.literal_eval(line)
          line = " ".join(token for token in parsed if token)
        except Exception as e:
          logger.error("Error during parsing stdout line")
          logger.error(e)
      logger.info(f"[VOD] {line}")
  
    for raw in process.stderr:
      line = raw.strip()
      if line:
        logger.error(f"[VOD Error] {line}")

    exit_code = process.wait()
    elapsed = time.time() - start_time
    minutes = round(elapsed / 60, 2)

    if exit_code != 0:
      logger.error(f"[CLI] Exit with code {process.returncode}")
      return False
    logger.info(f"Download completed successfully in {minutes} minutes! <3")
    return True
  except FileNotFoundError:
    logger.error("TwitchDownloaderCLI.exe not found. Check TWITCH_DL_CLI_DIR in the options")
    return False

  except Exception as e:
    logger.error(f"Unexpected error while downloading VOD {video_id}")
    logger.error(e)
    return False

def download_chat(
  video_id: str,
  filename: str,
):
  # Chat download
  cfg = configs["twitch"].vod_download
  cmd = [
    os.path.join(TWITCH_DL_CLI_DIR, "TwitchDownloaderCLI.exe"),
    "chatdownload",
    "--id", str(video_id),
    "--output", os.path.join(VODS_DIR, filename, f"{filename}_chat.{cfg.chat.download_format}"),
    "--compression", cfg.chat.compression,
    "--threads", str(cfg.download_threads),
    "--embed-images", str(cfg.chat.embed_images),
    "--bttv", str(cfg.chat.bttv),    
    "--ffz", str(cfg.chat.ffz),
    "--stv", str(cfg.chat.stv),    
    "--timestamp-format", cfg.chat.timestamp_format,
    "--collision", "Rename" 
  ]
  logger.debug("Running cmd: " + " ".join(
    f'"{str(c)}"' if " " in str(c) else str(c)
    for c in cmd
  ))

  logger.info(f"Starting download of Chat @ {filename}")

  start_time = time.time()

  try:
    process = subprocess.Popen(
      cmd,
      cwd=TWITCH_DL_CLI_DIR,
      stdout=subprocess.PIPE,
      stderr=subprocess.PIPE,
      text = True,
      bufsize= 1
    )
  
    for raw in process.stdout:
      line = raw.strip()
      if not line: 
        continue
      if line.startswith("[") and line.endswith("]") and "'" in line:
        try:
          parsed = ast.literal_eval(line)
          line = " ".join(token for token in parsed if token)
        except Exception as e:
          logger.error("Error during parsing stdout line")
          logger.error(e)
      logger.info(f"[CHAT EXPORT] {line}")
  
    for raw in process.stderr:
      line = raw.strip()
      if line:
        logger.error(f"[CHAT EXPORT Error] {line}")

    exit_code = process.wait()
    elapsed = time.time() - start_time
    minutes = round(elapsed / 60, 2)

    if exit_code != 0:
      logger.error(f"[CLI] Exit with code {process.returncode}")
      return False
    logger.info(f"Download completed successfully in {minutes} minutes! <3")
    return True
  except FileNotFoundError:
    logger.error("TwitchDownloaderCLI.exe not found. Check TWITCH_DL_CLI_DIR in the options")
    return False

  except Exception as e:
    logger.error(f"Unexpected error while downloading CHAT {video_id}")
    logger.error(e)
    return False

def download_chat_as_render(
  filename: str,
):
  # Chat download (as render)
  cfg = configs["twitch"].vod_download
  cmd = [
    os.path.join(TWITCH_DL_CLI_DIR, "TwitchDownloaderCLI.exe"),
    "chatrender",
    "--input", os.path.join(VODS_DIR, filename, f"{filename}_chat.json"),
    "--output", os.path.join(VODS_DIR, filename, f"{filename}_chat_render.mp4"),

    "--bttv", str(cfg.chat_render.bttv),
    "--ffz", str(cfg.chat_render.ffz),
    "--stv", str(cfg.chat_render.stv),
    
    "--background-color", f"#{cfg.chat_render.background_color}",
    "--alternate-backgrounds", str(cfg.chat_render.alternate_backgrounds),
    "--alt-background-color", f"#{cfg.chat_render.alt_background_color}",
    "--readable-colors", str(cfg.chat_render.readable_colors),
    "--message-color", f"#{cfg.chat_render.message_color}",

    "--chat-width", str(cfg.chat_render.width),
    "--chat-height", str(cfg.chat_render.height),

    "--allow-unlisted-emotes", str(cfg.chat_render.allow_unlisted_emotes),

    "--sub-messages", str(cfg.chat_render.sub_messages),
    "--badges", str(cfg.chat_render.badges),
    "--outline", str(cfg.chat_render.outline),
    "--outline-size", str(cfg.chat_render.outline_size),

    "--font", str(cfg.chat_render.font),
    "--font-size", str(cfg.chat_render.font_size),

    "--message-fontstyle", str(cfg.chat_render.message_fontstyle),
    "--username-fontstyle", str(cfg.chat_render.username_fontstyle),

    "--timestamp", str(cfg.chat_render.timestamp),
    "--generate-mask", str(cfg.chat_render.generate_mask),
    "--sharpening", str(cfg.chat_render.sharpening),

    "--framerate", str(cfg.chat_render.framerate),
    "--update-rate", str(cfg.chat_render.update_rate),

    "--ignore-users", str(cfg.chat_render.ignore_users),
    "--ban-words", str(cfg.chat_render.ban_words),

    "--badge-filter", str(cfg.chat_render.badge_filter),
    "--dispersion", str(cfg.chat_render.dispersion),
    "--avatars", str(cfg.chat_render.avatars),
    "--offline", str(cfg.chat_render.offline),

    "--emoji-vendor", str(cfg.chat_render.emoji_vendor),
    "--skip-drive-waiting", str(cfg.chat_render.skip_drive_waiting),

    "--scale-emote", str(cfg.chat_render.scale_emote),
    "--scale-badge", str(cfg.chat_render.scale_badge),
    "--scale-emoji", str(cfg.chat_render.scale_emoji),
    "--scale-avatar", str(cfg.chat_render.scale_avatar),

    "--scale-vertical", str(cfg.chat_render.scale_vertical),
    "--scale-side-padding", str(cfg.chat_render.scale_side_padding),
    "--scale-section-height", str(cfg.chat_render.scale_section_height),
    "--scale-word-space", str(cfg.chat_render.scale_word_space),
    "--scale-emote-space", str(cfg.chat_render.scale_emote_space),
    "--scale-highlight-stroke", str(cfg.chat_render.scale_highlight_stroke),
    "--scale-highlight-indent", str(cfg.chat_render.scale_highlight_indent),

    # "--input-args", str(cfg.chat_render.input_args),
    # "--output-args", str(cfg.chat_render.output_args),
    "--ffmpeg-path", os.path.join(FFMPEG_PATH_DIR, "ffmpeg.exe"),
    "--collision", "Rename"
  ]

  logger.debug("Running cmd: " + " ".join(
    f'"{str(c)}"' if " " in str(c) else str(c)
    for c in cmd
  ))

  logger.info(f"Starting rendering of Chat @ {filename}")
  try:
    process = subprocess.Popen(
      cmd,
      cwd=TWITCH_DL_CLI_DIR,
      stdout=subprocess.PIPE,
      stderr=subprocess.PIPE,
      text = True,
      bufsize= 1
    )
    percent_re = re.compile(r"Rendering Video (\d+)%")
    last_percent = -1

    try:
        for raw in process.stdout:
            line = raw.strip()
            if not line:
                continue

            # Parse bracketed list output: ['a', 'b', 'c']
            if line.startswith("[") and line.endswith("]") and "'" in line:
                try:
                    parsed = ast.literal_eval(line)
                    line = " ".join(token for token in parsed if token)
                except Exception as e:
                    logger.error("Error during parsing stdout line")
                    logger.error(e)

            # Detect percentage updates
            match = percent_re.search(line)
            if match:
                percent = int(match.group(1))
                if percent != last_percent:
                    logger.info(f"[CHAT RENDER] {line}")
                    last_percent = percent
                continue

            # Normal log line
            logger.info(f"[CHAT RENDER] {line}")

        # STDERR
        for raw in process.stderr:
            line = raw.strip()
            if line:
                logger.error(f"[CHAT RENDER Error] {line}")

        exit_code = process.wait()

        if exit_code != 0:
            logger.error(f"[CLI] Exit with code {process.returncode}")
            return False

        logger.info("Rendering completed successfully! <3")
        return True

    except FileNotFoundError:
        logger.error("TwitchDownloaderCLI.exe not found. Check TWITCH_DL_CLI_DIR in the options")
        return False

  except Exception as e:
        logger.error(f"Unexpected error while rendering CHAT {filename}")
        logger.error(e)
        return False


# ============================================================================
# Async wrapper for use with the download queue
# ============================================================================

async def download_latest_video_async(time_of_event, broadcaster_id, stream_id=None):
  """Async wrapper for download_latest_video.
  
  This function runs the synchronous download_latest_video in a thread pool
  to prevent blocking the event loop during long downloads.
  
  Args:
    time_of_event: ISO 8601 timestamp of when stream ended.
    broadcaster_id: The broadcaster's user ID.
    stream_id: Optional specific stream_id to download.
  
  Returns:
    True if download was successful, False otherwise.
  """
  import asyncio
  
  loop = asyncio.get_event_loop()
  try:
    result = await loop.run_in_executor(
      None,  # Use default thread pool
      download_latest_video,
      time_of_event,
      broadcaster_id,
      stream_id
    )
    return result
  except Exception as e:
    logger.error(f"Async download wrapper exception: {e}")
    return False

