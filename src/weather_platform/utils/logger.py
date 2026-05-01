"""Logging configuration utilities.

This module provides centralized logging setup for application and CLI usage.
Configures Python logging with appropriate formatters for production environments.
"""
import logging


def configure_logging(level: str = "INFO") -> None:
    """Configure Python logging with timestamp, level, logger name, and message.
    
    Applies a consistent log format across the application suitable for
    both console and log aggregation systems.
    
    Log Format: "YYYY-MM-DD HH:MM:SS LEVEL logger_name message"
    
    Args:
        level: Logging level as string (INFO, DEBUG, WARNING, ERROR, CRITICAL).
               Defaults to INFO. Case-insensitive.
               
    Example:
        configure_logging("DEBUG")  # Enable debug logging
        configure_logging("WARNING")  # Only warnings and errors
    """
    # Convert level string to logging constant (e.g., "INFO" -> logging.INFO)
    # Defaults to INFO if invalid level provided
    logging_level = getattr(logging, level.upper(), logging.INFO)
    
    # Configure root logger with consistent format
    logging.basicConfig(
        level=logging_level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
