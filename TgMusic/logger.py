#  Copyright (c) 2025 AshokShau
#  Licensed under the GNU AGPL v3.0: https://www.gnu.org/licenses/agpl-3.0.html
#  Part of the TgMusicBot project. All rights reserved where applicable.
#  Modified by Devin - Major modifications and improvements


import logging
import os
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from pathlib import Path

# Create logs directory if it doesn't exist
Path("logs").mkdir(exist_ok=True)

# Enhanced log format with more details
LOG_FORMAT = (
    "[%(asctime)s - %(levelname)s] - %(name)s - "
    "%(filename)s:%(lineno)d - %(funcName)s - %(message)s"
)

# Different formats for different handlers
DETAILED_FORMAT = (
    "[%(asctime)s - %(levelname)s] - %(name)s - "
    "%(filename)s:%(lineno)d - %(funcName)s - %(message)s"
)

SIMPLE_FORMAT = "[%(asctime)s - %(levelname)s] - %(message)s"

# Create formatters
detailed_formatter = logging.Formatter(DETAILED_FORMAT, datefmt="%Y-%m-%d %H:%M:%S")
simple_formatter = logging.Formatter(SIMPLE_FORMAT, datefmt="%H:%M:%S")

# Console handler with simple format
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(simple_formatter)
console_handler.setLevel(logging.INFO)

# File handler with detailed format and rotation
file_handler = RotatingFileHandler(
    "logs/bot.log",
    maxBytes=5 * 1024 * 1024,  # 5 MB
    backupCount=5,
    encoding="utf-8",
)
file_handler.setFormatter(detailed_formatter)
file_handler.setLevel(logging.DEBUG)

# Error log handler
error_handler = RotatingFileHandler(
    "logs/errors.log",
    maxBytes=2 * 1024 * 1024,  # 2 MB
    backupCount=3,
    encoding="utf-8",
)
error_handler.setFormatter(detailed_formatter)
error_handler.setLevel(logging.ERROR)

# Performance log handler
perf_handler = TimedRotatingFileHandler(
    "logs/performance.log",
    when="midnight",
    interval=1,
    backupCount=7,
    encoding="utf-8",
)
perf_handler.setFormatter(detailed_formatter)
perf_handler.setLevel(logging.INFO)

# Configure root logger
root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)
root_logger.addHandler(console_handler)
root_logger.addHandler(file_handler)
root_logger.addHandler(error_handler)

# Create performance logger
PERF_LOGGER = logging.getLogger("TgMusicBot.Performance")
PERF_LOGGER.addHandler(perf_handler)
PERF_LOGGER.setLevel(logging.INFO)

# Suppress noisy libraries
for lib in ("httpx", "pyrogram", "apscheduler", "urllib3", "asyncio"):
    logging.getLogger(lib).setLevel(logging.WARNING)

# Set specific levels for debugging (uncomment as needed)
# logging.getLogger("pytgcalls").setLevel(logging.DEBUG)
# logging.getLogger("ffmpeg").setLevel(logging.DEBUG)
# logging.getLogger("ntgcalls").setLevel(logging.DEBUG)
# logging.getLogger("webrtc").setLevel(logging.DEBUG)

# Main bot logger
LOGGER = logging.getLogger("TgMusicBot")

# Custom log levels for better categorization
class PerformanceFilter(logging.Filter):
    """Filter for performance-related logs."""
    
    def filter(self, record):
        return "performance" in record.getMessage().lower() or "duration" in record.getMessage().lower()

class ErrorFilter(logging.Filter):
    """Filter for error-related logs."""
    
    def filter(self, record):
        return record.levelno >= logging.ERROR

# Apply filters
perf_handler.addFilter(PerformanceFilter())
error_handler.addFilter(ErrorFilter())

# Log startup information
LOGGER.info("=" * 60)
LOGGER.info("TgMusicBot Starting...")
LOGGER.info(f"Python Version: {sys.version}")
LOGGER.info(f"Log Level: {logging.getLevelName(LOGGER.level)}")
LOGGER.info("=" * 60)
