"""
logger.py – Loguru-based application logger
"""
import sys
from loguru import logger

# Remove the default handler
logger.remove()

# Pretty console output
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{line}</cyan> – <level>{message}</level>",
    level="DEBUG",
    colorize=True,
)

# Rotating file log
logger.add(
    "logs/app.log",
    rotation="10 MB",
    retention="30 days",
    compression="zip",
    level="INFO",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{line} – {message}",
)

__all__ = ["logger"]
