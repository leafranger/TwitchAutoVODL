import os
from pathlib import Path

ROOT_DIR          = Path(__file__).parent.parent
CONFIG_DIR        = os.path.join(ROOT_DIR, "config")
STATE_DIR         = os.path.join(ROOT_DIR, "state")
UTILS_DIR         = os.path.join(ROOT_DIR, "utils")
VODS_DIR          = os.path.join(ROOT_DIR, "vods")
TWITCH_DL_CLI_DIR = os.path.join(ROOT_DIR, "twitch_downloader_cli")
FFMPEG_PATH_DIR   = os.path.join(TWITCH_DL_CLI_DIR, "ffmpeg")
