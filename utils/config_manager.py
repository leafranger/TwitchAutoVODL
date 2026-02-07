import yaml
import os
from munch import munchify
from utils.project_definitions import CONFIG_DIR

_LOGGING_CONFIG_DIR = os.path.join(CONFIG_DIR, "logging.yaml")
_AUTH_CONFIG_DIR    = os.path.join(CONFIG_DIR, "twitch.yaml")

configs = {}

def _initialize_configs():
  # Load logging configuration
  if os.path.exists(_LOGGING_CONFIG_DIR):
    with open(_LOGGING_CONFIG_DIR, "r") as f:
      configs["logging"] = yaml.safe_load(f)

  # Load auth configuration
  if os.path.exists(_AUTH_CONFIG_DIR):
    with open(_AUTH_CONFIG_DIR, "r") as f:
      configs["twitch"] = munchify(yaml.safe_load(f))

_initialize_configs()
