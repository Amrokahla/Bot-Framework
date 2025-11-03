"""
Command registration and management.
"""
import logging
from typing import Callable, Dict, Optional

logger = logging.getLogger(__name__)


class CommandRegistry:
    """Manages command registration and lookup."""

    def __init__(self):
        self.commands: Dict[str, Dict] = {}

    def register(self, command: str, handler_func: Callable, required_role: Optional[str] = "user"):
        """
        Register a new command with its handler and required role.
        
        Args:
            command: Command name without / prefix
            handler_func: Callback function(message) to handle command
            required_role: Minimum role required to use command (None means no restriction)
        """
        self.commands[command] = {
            'handler': handler_func,
            'role': required_role
        }
        logger.debug(f"Registered command /{command} requiring role: {required_role}")

    def get_handler(self, command: str) -> Optional[Callable]:
        """Get handler for a command."""
        cmd_info = self.commands.get(command)
        return cmd_info['handler'] if cmd_info else None

    def get_required_role(self, command: str) -> Optional[str]:
        """Get required role for a command."""
        cmd_info = self.commands.get(command)
        return cmd_info['role'] if cmd_info else None

    def has_command(self, command: str) -> bool:
        """Check if command is registered."""
        return command in self.commands

    def get_all_commands(self) -> Dict[str, Dict]:
        """Get all registered commands."""
        return self.commands.copy()
