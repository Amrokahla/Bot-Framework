"""
Built-in system command handlers.
"""
import logging

logger = logging.getLogger(__name__)


class SystemCommands:
    """Handlers for built-in system commands."""

    def __init__(self, bot, user_manager, access_control):
        self.bot = bot
        self.user_manager = user_manager
        self.access_control = access_control

    def handle_start(self, message) -> None:
        """Handle /start command."""
        username = getattr(message.from_user, 'first_name', None)
        if username:
            welcome_text = f"👋 Welcome {username}! Use /help to see available commands."
        else:
            welcome_text = "👋 Welcome! Use /help to see available commands."
        self.bot.send_message(message.chat.id, welcome_text)

    def handle_help(self, message) -> None:
        """Handle /help command."""
        user_id = message.from_user.id
        role_hierarchy = ["user", "admin", "superadmin"]
        user_role = self.access_control.role_manager.get_role(user_id) or "user"
        try:
            user_level = role_hierarchy.index(user_role)
        except ValueError:
            user_level = 0

        user_cmds = ["start", "help", "info"]
        admin_cmds = ["broadcast", "schedule_message", "list_scheduled", "cancel_scheduled", "settings", "set"]
        superadmin_cmds = ["promote_user", "demote_user"]
        command_descriptions = {
            "start": "/start - Start interaction",
            "help": "/help - Show this help message",
            "info": "/info - Bot info",
            "broadcast": "/broadcast - Send a message to all users",
            "schedule_message": "/schedule_message - Schedule a message",
            "list_scheduled": "/list_scheduled - View pending scheduled messages",
            "cancel_scheduled": "/cancel_scheduled - Cancel scheduled messages",
            "settings": "/settings - View current bot settings",
            "set": "/set - Change bot settings",
            "promote_user": "/promote_user <user_id> <role> - Promote user to role (superadmin only)",
            "demote_user": "/demote_user <user_id> - Demote user to lower role (superadmin only)"
        }

        help_lines = ["Bot Help"]
        help_lines.append("")
        help_lines.append("User Commands:")
        for cmd in user_cmds:
            help_lines.append(f"  {command_descriptions[cmd]}")

        if user_level >= 1:
            help_lines.append("")
            help_lines.append("Admin Commands:")
            for cmd in admin_cmds:
                help_lines.append(f"  {command_descriptions[cmd]}")

        if user_level >= 2:
            help_lines.append("")
            help_lines.append("Superadmin Commands:")
            for cmd in superadmin_cmds:
                help_lines.append(f"  {command_descriptions[cmd]}")

        # Add plugin commands
        if hasattr(self.bot, "plugins"):
            for pname, plugin in self.bot.plugins.items():
                if plugin.is_active() and hasattr(plugin, "commands"):
                    # Check if user has permission to see this plugin's commands
                    allowed_roles = getattr(plugin, "allowed_roles", ["admin", "superadmin"])
                    if not self._check_plugin_access(user_role, allowed_roles):
                        continue  # Skip this plugin if user doesn't have access
                    
                    plugin_cmds = plugin.commands()
                    if plugin_cmds:
                        help_lines.append("")
                        help_lines.append(f"{pname.capitalize()} Plugin Commands:")
                        for cmd, desc in plugin_cmds.items():
                            help_lines.append(f"  {cmd} - {desc}")

        help_text = "\n".join(help_lines)

        privileged_roles = ["admin", "superadmin"]
        if message.chat.type in ["group", "supergroup"] and user_role in privileged_roles:
            try:
                self.bot.send_message(user_id, help_text)
                self.bot.send_message(message.chat.id, "Sent your role commands privately.")
            except Exception as e:
                logger.error(f"Failed to DM help: {e}")
                self.bot.send_message(message.chat.id, "Could not send help DM.")
        else:
            self.bot.send_message(message.chat.id, help_text)

    def handle_info(self, message) -> None:
        """Handle /info command."""
        bot_username = getattr(self.bot, 'username', None) or "Bot"
        tz = None
        lang = None
        try:
            tz = getattr(getattr(self.bot, 'admin_tools', None), 'settings_manager', None)
            if tz:
                tz = tz.get('timezone')
                lang = tz.get('language')
        except Exception:
            pass
        info_text = (
            f"🤖 Bot: @{bot_username}\n"
            f"🌍 Timezone: {tz or 'Africa/Cairo'}\n"
            f"🌐 Language: {lang or 'en'}\n"
        )
        self.bot.send_message(message.chat.id, info_text)

    def _check_plugin_access(self, user_role, allowed_roles):
        """
        Check if user_role is allowed based on allowed_roles list.
        
        Args:
            user_role: User's current role
            allowed_roles: List of allowed roles for the plugin
            
        Returns:
            bool: True if user has access, False otherwise
        """
        if not allowed_roles:
            return False
        
        if "all" in allowed_roles:
            return True
        
        role_hierarchy = {"user": 1, "admin": 2, "superadmin": 3}
        user_level = role_hierarchy.get(user_role, 0)
        
        for allowed_role in allowed_roles:
            allowed_level = role_hierarchy.get(allowed_role.lower(), 0)
            if user_level >= allowed_level:
                return True
        
        return False
