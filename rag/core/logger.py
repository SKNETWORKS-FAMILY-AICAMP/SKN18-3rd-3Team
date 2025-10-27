"""Structured logging configuration"""

import logging
import sys
from typing import Optional


def get_logger(
    name: str,
    level: Optional[str] = None
) -> logging.Logger:
    """
    Get or create a structured logger.
    
    Args:
        name: Logger name (typically __name__)
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    
    # Only configure if not already configured
    if not logger.handlers:
        # Set level
        if level is None:
            from .config import get_config
            try:
                config = get_config()
                level = config.LOG_LEVEL
            except Exception:
                level = "INFO"
        
        logger.setLevel(getattr(logging, level.upper()))
        
        # Create console handler
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(getattr(logging, level.upper()))
        
        # Create formatter
        formatter = logging.Formatter(
            fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)
        
        # Add handler to logger
        logger.addHandler(handler)
        
        # Prevent propagation to root logger
        logger.propagate = False
    
    return logger
