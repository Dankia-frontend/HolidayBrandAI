# logger.py
import logging
from logging.handlers import TimedRotatingFileHandler
import os

# Create logs directory
os.makedirs("logs", exist_ok=True)

# Formatter
formatter = logging.Formatter(
    "%(asctime)s - [%(levelname)s] - %(name)s - %(message)s"
)

# Rotate every 6 hours (when='h', interval=6)
# Keep only the last 4 rotations (≈ 24 hours of logs)
info_handler = TimedRotatingFileHandler(
    "logs/app_info.log", when="h", interval=6, backupCount=4, encoding="utf-8"
)
info_handler.setFormatter(formatter)
info_handler.setLevel(logging.INFO)

error_handler = TimedRotatingFileHandler(
    "logs/app_errors.log", when="h", interval=6, backupCount=4, encoding="utf-8"
)
error_handler.setFormatter(formatter)
error_handler.setLevel(logging.ERROR)

# Main logger
logger = logging.getLogger("AppLogger")
logger.setLevel(logging.INFO)
logger.addHandler(info_handler)
logger.addHandler(error_handler)

# Optional: console output too
console = logging.StreamHandler()
console.setFormatter(formatter)
logger.addHandler(console)

def get_logger(name: str):
    """Return a child logger with a module-specific name."""
    return logger.getChild(name)
