"""
Shared utility functions for the bot core components.
"""

import logging
import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
import pytz

logger = logging.getLogger(__name__)

# Message formatting helpers
def format_message(template: str, **kwargs) -> str:
    """Format a message template with variables."""
    try:
        return template.format(**kwargs)
    except KeyError as e:
        logger.error(f"Missing template variable: {e}")
        return template
    except Exception as e:
        logger.error(f"Message format error: {e}")
        return template

def truncate_text(text: str, max_length: int = 100) -> str:
    """Safely truncate text to max_length with ellipsis."""
    if len(text) <= max_length:
        return text
    return text[:max_length-3] + "..."

# Command parsing
def parse_command(text: str) -> tuple[str, List[str]]:
    """
    Parse a command message into command and args.
    
    Args:
        text: Raw message text like "/command arg1 arg2"
        
    Returns:
        Tuple of (command, [args])
    """
    parts = text.split()
    if not parts:
        return "", []
        
    command = parts[0][1:]  # Remove leading /
    if '@' in command:  # Handle /command@botname
        command = command.split('@')[0]
        
    return command.lower(), parts[1:]

def validate_command(args: List[str], min_args: int = 0, max_args: Optional[int] = None) -> bool:
    """
    Validate command argument count.
    
    Args:
        args: List of command arguments
        min_args: Minimum required arguments
        max_args: Maximum allowed arguments (None for unlimited)
    """
    if len(args) < min_args:
        return False
    if max_args is not None and len(args) > max_args:
        return False
    return True

# Time handling
def parse_time(time_str: str, timezone: str = "UTC") -> Optional[datetime]:
    """
    Parse time string into datetime.
    Handles common formats like "YYYY-MM-DD HH:MM".
    
    Args:
        time_str: Time string to parse
        timezone: Timezone name (e.g. "UTC", "Europe/London")
        
    Returns:
        datetime object or None if parsing fails
    """
    formats = [
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%d-%m-%Y %H:%M",
        "%d/%m/%Y %H:%M",
    ]
    
    tz = pytz.timezone(timezone)
    
    for fmt in formats:
        try:
            dt = datetime.strptime(time_str, fmt)
            return tz.localize(dt)
        except ValueError:
            continue
            
    return None

# Data handling
def safe_json_loads(text: str, default: Any = None) -> Any:
    """Safely parse JSON with fallback."""
    try:
        return json.loads(text)
    except Exception as e:
        logger.error(f"JSON parse error: {e}")
        return default

def safe_json_dumps(obj: Any) -> str:
    """Safely convert to JSON with fallback."""
    try:
        return json.dumps(obj)
    except Exception as e:
        logger.error(f"JSON dump error: {e}")
        return str(obj)

# Role helpers
def compare_roles(role1: str, role2: str, hierarchy: List[str]) -> int:
    """
    Compare two roles in hierarchy.
    Returns:
        1 if role1 > role2
        0 if role1 == role2
        -1 if role1 < role2
    """
    try:
        idx1 = hierarchy.index(role1)
        idx2 = hierarchy.index(role2)
        return (idx1 > idx2) - (idx1 < idx2)
    except ValueError:
        return -1  # Unknown roles are treated as lowest

# Validation
def is_valid_username(username: str) -> bool:
    """Check if username follows Telegram's rules."""
    if not username:
        return False
    return (
        len(username) >= 5 
        and len(username) <= 32
        and username.isalnum()
        or '_' in username
    )

def is_valid_user_id(user_id: Union[int, str]) -> bool:
    """Check if user_id is valid Telegram ID."""
    try:
        uid = int(user_id)
        return uid > 0
    except (ValueError, TypeError):
        return False