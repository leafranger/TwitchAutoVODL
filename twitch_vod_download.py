import ast
from datetime import datetime
from nt import mkdir
import os
import re
import subprocess
import time
import requests
from utils.log_util import get_logger
logger = get_logger(__name__)
from utils.config_manager import configs
import utils.auth_state_manager as auth
from twitch_auth import TWITCH_CLIENT_ID
import utils.latest_stream_state_manager as last_stream
from utils.project_definitions import TWITCH_DL_CLI_DIR, FFMPEG_PATH_DIR, VODS_DIR

def save_latest_stream_info(stream_info):
  last_stream.set_stream_id(stream_info["id"])
  last_stream.set_created_at(stream_info["created_at"])

def get_user_videos(broadcaster_id):
  
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
    return response.json().get("data")
  except Exception as e:
    logger.error(f"Error getting latest [{broadcaster_id}]'s last {n_of_videos} videos")
    logger.error(e)
    return None

def parse_iso_z(timestamp:str)->datetime:
  # Keeping up to microseconds
  if timestamp.endswith("Z"):
    timestamp = timestamp[:-1] + "+00:00"
  # Trimming fractional seconds
  if "." in timestamp:
    timestamp = timestamp.split(".",1)[0]+"Z"
  return datetime.fromisoformat(timestamp)

def timestamp_to_seconds(tmp:str)->int:
  return int(datetime.timestamp(datetime.fromisoformat(tmp)))

def get_timestamp_difference(timestamp_new:str, timestamp_old:str)->int:
  dt1 = parse_iso_z(timestamp_new)
  dt2 = parse_iso_z(timestamp_old)
  delta = dt1-dt2
  return int(delta.total_seconds())

# # Given the latest videos, check if the latest is available
# def check_if_video_published(time_of_event, broadcaster_id):
#   logger.debug("Checking if video is published...")
#   cfg = configs["twitch"].vod_download
#   videos_data = get_user_videos(broadcaster_id)
#   if not videos_data:
#     return False

#   # Get the latest video from the bunch  
#   latest_video = None

#   def save_video(video):
#     return {
#       "id": video["id"],
#       "stream_id": video["stream_id"],
#       "title": video["title"],
#       "created_at": video["created_at"],
#     }

#   for video in videos_data:
#     # logger.debug(f"Checking Video: {video["id"]}; Stream: {video["stream_id"]}; '{video["title"]}'")
#     if video["type"] != "archive":
#       logger.debug(f"Video {video["id"]} is not type archive"); break

#     if video["viewable"] != "public":
#       logger.debug(f"Video {video["id"]} is not public yet"); break

#     if video["published_at"] == None:
#       logger.debug(f"Video {video["id"]} not yet published"); break

#     if video["stream_id"] == None:
#       logger.debug(f"Video {video["id"]} is not a stream"); break

#     if latest_video == None:
#       logger.debug("First video set")
#       latest_video=save_video(video)
#     else:
#       video_start_time = timestamp_to_seconds(video["created_at"])
#       latest_video_start_time = timestamp_to_seconds(latest_video["created_at"])
#       if video_start_time > latest_video_start_time:
#         latest_video = save_video(video)   
  
#   # Time difference betwwen websocket event and video publish timestamp
#   time_difference = get_timestamp_difference(time_of_event, latest_video["published_at"])
#   logger.debug(f"Difference between websocket event and video timestamp: {time_difference}")
#   # Timespan in which the video was published since the websocket event
#   availability_timespan = cfg.fetch_retry_cooldown * cfg.fetch_max_retries
#   logger.debug(f"Max timespan of availability [CD: {cfg.fetch_retry_cooldown}; RE: {cfg.fetch_max_retries}]: {availability_timespan}")
#   # Checking if video was published during check time
#   if time_difference > availability_timespan:
#     # Too much difference, video was published before websocket event
#     return False
#   else:
#     # Video was 
#     return True

# Given the latest videos, check if the latest is available
def check_if_video_published(broadcaster_id):
  logger.debug("Checking if video is published...")
  videos_data = get_user_videos(broadcaster_id)
  if not videos_data:
    return False

  # Check conresponding stream
  latest_stream_id = last_stream.get_stream_id()
  is_stream_ready_for_download = False


  for video in videos_data:
    # logger.debug(f"Checking Video: {video["id"]}; Stream: {video["stream_id"]}; '{video["title"]}'")
    if video["stream_id"] == latest_stream_id:
      logger.info("Latest stream found")
      if video["type"] != "archive":
        logger.warning(f"Video {video["id"]} is not type archive"); break

      if video["viewable"] != "public":
        logger.warning(f"Video {video["id"]} is not public yet"); break

      if video["published_at"] == None:
        logger.warning(f"Video {video["id"]} not yet published"); break

      if video["stream_id"] == None:
        logger.warning(f"Video {video["id"]} is not a stream"); break
      is_stream_ready_for_download = True
      last_stream.set_video_id(video["id"])
  return is_stream_ready_for_download

def is_video_downloadable(broadcaster_id):
  cfg = configs["twitch"].vod_download
  max_retries = cfg.fetch_max_retries
  cooldown = cfg.fetch_retry_cooldown
  for retry in range(max_retries):
    logger.debug(f"Attempt #{retry+1}...")
    is_video_available = check_if_video_published(broadcaster_id)
    if is_video_available:
      
      return True
    else:
      logger.warning(f"Attempt #{retry+1} failed, next retry in {cooldown}s...")
      time.sleep(cooldown)
  logger.warning(f"Stream was not available for download in the latest {max_retries * cooldown} seconds")
  return False

def download_latest_video(time_of_event, broadcaster_id, video_id):
  # DEBUG
  logger.debug("DEBUG ONLY, REMOVE LATER")
  broadcaster_id = auth.get_user_id()
  if is_video_downloadable(broadcaster_id=broadcaster_id):
    # VOD Download
    broadcaster = auth.get_user_login()
    filename = f"{broadcaster}_{time_of_event}_{video_id}.mp4"
    download_video(video_id, filename)

    # Chat JSON Download

    # Chat Render Download
  


# Remember to use video_id and not stream_id
def download_video(
  video_id: str,
  filename: str,
):
  # Video download
  cfg = configs["twitch"].vod_download
  cmd = [
    os.path.join(TWITCH_DL_CLI_DIR, "TwitchDownloaderCLI.exe"),
    "videodownload",
    "--id", str(video_id),
    "--output", os.path.join(VODS_DIR, f"{filename}.{cfg.vods.download_format}"),
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
    "--output", os.path.join(VODS_DIR, f"{filename}.{cfg.chat.download_format}"),
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
    "--input", os.path.join(VODS_DIR, f"{filename}.json"),
    "--output", os.path.join(VODS_DIR, f"{filename}.mp4"),

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
  


  
