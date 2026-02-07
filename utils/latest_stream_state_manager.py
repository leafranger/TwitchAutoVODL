import json
import os
from utils.log_util import get_logger
from utils.project_definitions import STATE_DIR
logger = get_logger(__name__)

LATEST_STREAM_STATE_FILE_PATH = os.path.join(STATE_DIR, "latest_stream.json")

def _get_info(info_name:str):
  latest_live_state = load_latest_live_state()
  
  if latest_live_state is None:
    logger.error("Latest live state is empty")
    return

  info = latest_live_state.get(info_name)
  if info is None:
    logger.error(f"{info_name} not found")
    return
  logger.debug(f"Got {info}")
  return info
def _set_info(info_name:str, info):
  latest_live_state = load_latest_live_state()
  
  if latest_live_state is None:
    logger.error("Latest live state is empty")
    return

  latest_live_state[info_name] = info
  with open(LATEST_STREAM_STATE_FILE_PATH, "w") as f:
    logger.debug(f"Setting {info_name} to {info}")
    json.dump(latest_live_state, f)

def load_latest_live_state():
  if not os.path.exists(LATEST_STREAM_STATE_FILE_PATH):
    logger.error("Latest live state file not found")
    return None
  with open(LATEST_STREAM_STATE_FILE_PATH, "r") as f:
    return json.load(f)

# stream id
def get_stream_id():
  logger.info("Getting stream id...")
  return _get_info("stream_id")
def set_stream_id(stream_id:str):
  logger.info("Setting stream id...")
  _set_info("stream_id", stream_id)

# video id
def get_video_id():
  logger.info("Getting video id...")
  return _get_info("video_id")
def set_video_id(video_id:str):
  logger.info("Setting video id...")
  _set_info("video_id", video_id)

# created at
def get_created_at():
  logger.info("Getting created at...")
  return _get_info("created_at")
def set_created_at(created_at:str):
  logger.info("Setting created at...")
  _set_info("created_at", created_at)  

# Save Latest live state to file
def save_latest_live_state(latest_live_state: dict):
  with open(LATEST_STREAM_STATE_FILE_PATH, "w") as f:
    json.dump(latest_live_state, f)

def clear_latest_live_state():
  if os.path.exists(LATEST_STREAM_STATE_FILE_PATH):
    os.remove(LATEST_STREAM_STATE_FILE_PATH)