# logger.py
import logging
from logging.handlers import TimedRotatingFileHandler
import os

# Ensure logs directory exists
os.makedirs("logs", exist_ok=True)

# Formatter for all logs
formatter = logging.Formatter(
    "%(asctime)s - [%(levelname)s] - %(name)s - %(message)s"
)

# ✅ Rotate every 1 hour and keep 24 backups (1 day total)
info_handler = TimedRotatingFileHandler(
    "logs/app_info.log", when="h", interval=1, backupCount=24, encoding="utf-8"
)
info_handler.setFormatter(formatter)
info_handler.setLevel(logging.INFO)

error_handler = TimedRotatingFileHandler(
    "logs/app_errors.log", when="h", interval=1, backupCount=24, encoding="utf-8"
)
error_handler.setFormatter(formatter)
error_handler.setLevel(logging.ERROR)

# Main logger
logger = logging.getLogger("AppLogger")
logger.setLevel(logging.INFO)
logger.addHandler(info_handler)
logger.addHandler(error_handler)

# Optional: Console output
console = logging.StreamHandler()
console.setFormatter(formatter)
logger.addHandler(console)

def get_logger(name: str):
    """Return a child logger with a module-specific name."""
    return logger.getChild(name)
