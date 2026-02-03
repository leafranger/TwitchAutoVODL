# Logging utility for the project
import logging
import logging.config
import yaml
import os

LOGGING_CONFIG_PATH = os.path.join(os.path.basename(__file__), "../config/logging.yaml")

# Load logging configuration from config folder
if os.path.exists(LOGGING_CONFIG_PATH):
  with open(LOGGING_CONFIG_PATH, "r") as f:
    logging_config = yaml.safe_load(f)

# Set up logging
logging.config.dictConfig(logging_config)

# Get logger
def get_logger(name: str):
  return logging.getLogger(name)


