"""
Main message routing and command handling system.
Refactored to use modular handlers.
"""
import logging
import re
from typing import Optional

from core.bot_authuntcator.user_manager import UserManager
from core.bot_authuntcator.access_control import AccessControl

from .command_registry import CommandRegistry
from .system_commands import SystemCommands
from .admin_commands import AdminCommands
from .plugin_handler import PluginHandler

logger = logging.getLogger(__name__)


class MessageHandler:
    """
    Core message routing and command handling system.
    Manages command registration and role-based access control.
    """

    def __init__(self, bot, user_manager: UserManager, access_control: AccessControl):
        self.bot = bot
        self.user_manager = user_manager
        self.access_control = access_control
        
        # Initialize modular components
        self.command_registry = CommandRegistry()
        self.system_commands = SystemCommands(bot, user_manager, access_control)
        self.admin_commands = AdminCommands(bot, user_manager, access_control)
        self.plugin_handler = PluginHandler(bot, access_control)
        
        # Register all system commands
        self._register_system_commands()

    def _register_system_commands(self):
        """Register built-in system commands."""
        # User commands
        self.command_registry.register("start", self.system_commands.handle_start, "user")
        self.command_registry.register("help", self.system_commands.handle_help, None)
        self.command_registry.register("info", self.system_commands.handle_info, "user")
        
        # Superadmin commands
        self.command_registry.register("promote_user", self.admin_commands.handle_promote_user, "superadmin")
        self.command_registry.register("demote_user", self.admin_commands.handle_demote_user, "superadmin")
        
        # Admin commands
        self.command_registry.register("create_poll", self.admin_commands.handle_create_poll, "admin")
        
        # Register admin_tools commands if available
        if hasattr(self.bot, "admin_tools"):
            self.command_registry.register("broadcast", self.bot.admin_tools._broadcast_handler, "admin")
            self.command_registry.register("schedule_message", self.bot.admin_tools._schedule_handler, "admin")
            self.command_registry.register("list_scheduled", self.bot.admin_tools._list_scheduled_handler, "admin")
            self.command_registry.register("cancel_scheduled", self.bot.admin_tools._cancel_scheduled_handler, "admin")
            self.command_registry.register("settings", self.bot.admin_tools.show_settings, "admin")
            self.command_registry.register("set", self.bot.admin_tools.set_setting, "admin")
        
        # Register plugin commands if plugins are active
        self.plugin_handler.register_plugin_commands(self.command_registry)

    def register_all_plugin_commands(self):
        """Register commands from all active plugins after both plugin activation and MessageHandler construction."""
        self.plugin_handler.register_plugin_commands(self.command_registry)

    def add_plugin_commands(self, plugin):
        """Register commands from a single plugin after activation."""
        self.plugin_handler.add_plugin_commands(plugin, self.command_registry)

    def register_command(self, command: str, handler_func, required_role: Optional[str] = "user"):
        """
        Register a new command with its handler and required role.
        
        Args:
            command: Command name without / prefix
            handler_func: Callback function(message) to handle command
            required_role: Minimum role required to use command
        """
        self.command_registry.register(command, handler_func, required_role)

    def handle_message(self, message) -> None:
        """
        Main message routing: if command, use command logic; if not, route to LLM if active, else ignore.
        """
        try:
            user_id = message.from_user.id
            chat_id = message.chat.id
            text = message.text or ""

            # Track user interaction
            username = getattr(message.from_user, 'username', None)
            self.user_manager.add_user(user_id, username, message.chat.type)

            # Use regex to detect commands (starts with / and only letters, numbers, underscores)
            command_match = re.match(r"^/([a-zA-Z0-9_]+)", text.strip())
            if command_match:
                self._handle_command(message)
                return

            # If not command, check LLM plugin
            llm_plugin = None
            if hasattr(self.bot, "plugins") and "llm" in self.bot.plugins:
                llm_plugin = self.bot.plugins["llm"]
            if llm_plugin and llm_plugin.is_active():
                reply = llm_plugin.respond_to_message(user_id, text)
                self.bot.send_message(chat_id, reply)
                return
            # If not command and no LLM, ignore
            return

        except Exception as e:
            logger.error(f"Error handling message: {e}", exc_info=True)
            self._send_error_message(message.chat.id)

    def _handle_command(self, message) -> None:
        """Process commands with role checking."""
        parts = (message.text or "").split()
        if not parts:
            return

        command = parts[0][1:].lower()  # Remove / and normalize
        if '@' in command:  # Handle commands like /help@botname
            command = command.split('@')[0]

        user_id = message.from_user.id
        
        # Generic security message - same for non-existent commands and unauthorized access
        security_message = "⚠️ This command either doesn't exist or you don't have permission to use it."
        
        if not self.command_registry.has_command(command):
            logger.warning(f"Command '{command}' not found in registry. User: {user_id}")
            # Don't reveal if command exists or not
            self.bot.send_message(message.chat.id, security_message)
            return

        # Check permissions
        required_role = self.command_registry.get_required_role(command)
        
        # Skip permission check if command has no role requirement
        if required_role is not None and not self.access_control.has_role(user_id, required_role):
            logger.warning(f"Access denied: {user_id} tried /{command} (requires {required_role})")
            # Use same generic message to avoid revealing command existence
            self.bot.send_message(message.chat.id, security_message)
            return

        # Execute handler
        try:
            handler = self.command_registry.get_handler(command)
            handler(message)
        except Exception as e:
            logger.error(f"Error in command /{command}: {e}", exc_info=True)
            self._send_error_message(message.chat.id)

    def _send_error_message(self, chat_id: int) -> None:
        """Send a generic error message."""
        self.bot.send_message(
            chat_id,
            "⚠️ Sorry, something went wrong processing that request."
        )
