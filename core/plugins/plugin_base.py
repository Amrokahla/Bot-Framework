from abc import ABC, abstractmethod
from typing import Dict, List, Any


class BasePlugin(ABC):
    """
    Abstract base class that defines the interface for all plugins.
    Each plugin should be fully self-contained, handling its own logic, commands, and configuration.
    """

    def __init__(self, bot, config: Dict[str, Any] = None):
        self.bot = bot
        self.config = config or {}
        self.active = False
        self.allowed_roles = ["admin", "superadmin"]  # Default to admin access

    @abstractmethod
    def name(self) -> str:
        """Unique name of the plugin (e.g. 'llm', 'weather', 'stats')."""
        pass

    @abstractmethod
    def description(self) -> str:
        """Short description of what this plugin does."""
        pass

    def activate(self):
        """Called when the plugin is activated."""
        self.active = True

    def deactivate(self):
        """Called when the plugin is deactivated."""
        self.active = False

    @abstractmethod
    def commands(self) -> Dict[str, str]:
        """
        Returns:
            A dict mapping command names to their descriptions.
            Example: {"/info": "Show plugin info", "/stop": "Stop current task"}
        """
        pass

    @abstractmethod
    def handle_command(self, command: str, args: List[str], user_id: int) -> str:
        """
        Handle incoming command directed to this plugin.
        Args:
            command: The command name (without '/')
            args: List of command arguments
            user_id: Telegram user ID of the sender
        Returns:
            A string response to be sent back to the user.
        """
        pass

    def is_active(self) -> bool:
        """Check if this plugin is currently active."""
        return self.active

    def help_text(self) -> str:
        """Return a nicely formatted help text for this plugin."""
        lines = [f"📦 *{self.name().capitalize()} Plugin*", self.description(), "", "Available commands:"]
        for cmd, desc in self.commands().items():
            lines.append(f"  {cmd} — {desc}")
        return "\n".join(lines)
