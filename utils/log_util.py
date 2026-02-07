# Logging utility for the project
import logging
import logging.config
from utils.config_manager import configs
import sys
from datetime import datetime

if hasattr(sys.stdout, "reconfigure"):
  sys.stdout.reconfigure(encoding="utf-8")

# Set up logging
logging.config.dictConfig(configs["logging"])

def _insert_session_break():
  root = logging.getLogger()
  for handler in root.handlers:
    if isinstance(handler, logging.FileHandler) and handler.stream:
      handler.acquire()
      try:
        handler.stream.write("\n\n\n")
        handler.stream.write("=" * 60 + "\n")
        handler.stream.write(f" NEW APPLICATION START - {datetime.utcnow().isoformat()}Z \n")
        handler.stream.write("=" * 60 + "\n")
        handler.flush()
      finally:
        handler.release()

_insert_session_break()

# Get logger
def get_logger(name: str):
  return logging.getLogger(name)

logger = get_logger(__name__)
# Toggle "websockets" library debug
if configs["twitch"].websocket.disable_websockets_client_debug_logging:
  logger.debug("Disabled Websockets DEBUG logging")
  logging.getLogger("websockets.client").setLevel(logging.WARNING)

