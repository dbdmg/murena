import os
import sys

from loguru import logger

LLM_LOG_DIR = os.path.join("logs", "llm_usage")


# Configure logger
def configure_logger():
    """
    Configures the loguru logger with rotation and retention policies.
    """
    # Remove default handler
    logger.remove()

    # Add console handler with color
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level="INFO",
        colorize=True,
    )

    # Add file handler with rotation (10 MB) and retention (1 week)
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    if not os.path.exists(LLM_LOG_DIR):
        os.makedirs(LLM_LOG_DIR)

    logger.add(
        os.path.join(log_dir, "app_{time:YYYY-MM-DD}.log"),
        rotation="10 MB",
        retention="1 week",
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        encoding="utf-8",
    )

    return logger


# Initialize logger
configure_logger()

# Globally disable markup parsing to avoid breaking with LLM output tags like <think>
logger = logger.opt(colors=False)

__all__ = ["logger", "LLM_LOG_DIR"]
