"""
Logging utility for SAR Narrative Generator
"""
import logging
import os
from logging.handlers import RotatingFileHandler
import sys
from pathlib import Path

# Fix the import
try:
    from ..config import LOG_DIR
except (ImportError, ValueError):
    # Fallback if relative import fails
    import sys
    from pathlib import Path
    sys.path.append(str(Path(__file__).resolve().parent.parent))
    from config import LOG_DIR

def get_logger(name):
    """
    Create a logger with the given name
    
    Args:
        name: Logger name (usually __name__)
    
    Returns:
        logging.Logger: Configured logger
    """
    # Create logger
    logger = logging.getLogger(name)
    
    # Only configure if not already configured
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        
        # Create formatters
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_formatter = logging.Formatter(
            '%(levelname)s - %(message)s'
        )
        
        # Create console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(console_formatter)
        
        # Ensure log directory exists
        os.makedirs(LOG_DIR, exist_ok=True)
        
        # Create file handler
        log_file = Path(LOG_DIR) / f"{name.split('.')[-1]}.log"
        file_handler = RotatingFileHandler(
            log_file, maxBytes=10*1024*1024, backupCount=5
        )
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(file_formatter)
        
        # Add handlers to logger
        logger.addHandler(console_handler)
        logger.addHandler(file_handler)
    
    return logger