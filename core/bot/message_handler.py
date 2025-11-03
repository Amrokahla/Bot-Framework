import logging
from typing import Callable, Dict, Optional
from core.bot_authuntcator.user_manager import UserManager
from core.bot_authuntcator.access_control import AccessControl

logger = logging.getLogger(__name__)

class MessageHandler:
    def add_plugin_commands(self, plugin):
        """Register commands from a single plugin after activation."""
        if plugin.is_active() and hasattr(plugin, "commands"):
            plugin_name = plugin.name()
            for cmd, desc in plugin.commands().items():
                cmd_name = cmd.lstrip("/").lower()
                # Create a handler that routes to the correct plugin
                handler = self._create_plugin_command_handler(plugin_name)
                self.register_command(cmd_name, handler, "admin")
    """
    Core message routing and command handling system.
    Manages command registration and role-based access control.
    """

    def __init__(self, bot, user_manager: UserManager, access_control: AccessControl):
        self.bot = bot
        self.user_manager = user_manager
        self.access_control = access_control
        self.command_registry: Dict[str, Dict] = {}
        self._register_system_commands()

    def register_all_plugin_commands(self):
        """Register commands from all active plugins after both plugin activation and MessageHandler construction."""
        active_plugins = getattr(self.bot, "active_plugins", [])
        if hasattr(self.bot, "plugins"):
            for pname, plugin in self.bot.plugins.items():
                if pname in active_plugins and plugin.is_active() and hasattr(plugin, "commands"):
                    for cmd, desc in plugin.commands().items():
                        cmd_name = cmd.lstrip("/").lower()
                        # Create a handler that routes to the correct plugin
                        handler = self._create_plugin_command_handler(pname)
                        self.register_command(cmd_name, handler, "admin")

    def _register_plugin_commands(self):
        """Register commands from active plugins (e.g., LLM) after activation."""
        active_plugins = getattr(self.bot, "active_plugins", [])
        if hasattr(self.bot, "plugins"):
            for pname, plugin in self.bot.plugins.items():
                if pname in active_plugins and plugin.is_active() and hasattr(plugin, "commands"):
                    for cmd, desc in plugin.commands().items():
                        cmd_name = cmd.lstrip("/").lower()
                        # Create a handler that routes to the correct plugin
                        handler = self._create_plugin_command_handler(pname)
                        self.register_command(cmd_name, handler, "admin")

    def _register_system_commands(self):
        """Register built-in system commands."""
        self.register_command("start", self._cmd_start, "user")
        self.register_command("help", self._cmd_help, None)  # None means no role requirement
        self.register_command("info", self._cmd_info, "user")
        # Superadmin commands
        self.register_command("promote_user", self._cmd_promote_user, "superadmin")
        self.register_command("demote_user", self._cmd_demote_user, "superadmin")
        # Admin commands
        self.register_command("create_poll", self._cmd_create_poll, "admin")
        # Always register admin_tools commands if available
        if hasattr(self.bot, "admin_tools"):
            self.register_command("broadcast", self.bot.admin_tools._broadcast_handler, "admin")
            self.register_command("schedule_message", self.bot.admin_tools._schedule_handler, "admin")
            self.register_command("list_scheduled", self.bot.admin_tools._list_scheduled_handler, "admin")
            self.register_command("cancel_scheduled", self.bot.admin_tools._cancel_scheduled_handler, "admin")
            self.register_command("settings", self.bot.admin_tools.show_settings, "admin")
            self.register_command("set", self.bot.admin_tools.set_setting, "admin")
        # Register plugin commands if plugins are active and in active_plugins
        active_plugins = getattr(self.bot, "active_plugins", [])
        if hasattr(self.bot, "plugins"):
            for pname, plugin in self.bot.plugins.items():
                if pname in active_plugins and plugin.is_active() and hasattr(plugin, "commands"):
                    for cmd, desc in plugin.commands().items():
                        cmd_name = cmd.lstrip("/").lower()
                        # Create a handler that routes to the correct plugin
                        handler = self._create_plugin_command_handler(pname)
                        self.register_command(cmd_name, handler, "admin")

    def _cmd_promote_user(self, message) -> None:
        """Promote a user to a higher role. Usage: /promote_user <user_id> <role>"""
        parts = (message.text or "").split()
        if len(parts) < 3:
            self.bot.send_message(message.chat.id, "Usage: /promote_user <user_id> <role>")
            return
        try:
            user_id = int(parts[1])
            new_role = parts[2]
            ok = self.user_manager.promote_user(user_id, new_role, by_user_id=message.from_user.id)
            if ok:
                # If promoted to admin, add to bot.admins and notify user
                if new_role == "admin" and hasattr(self.bot, "admins"):
                    if user_id not in self.bot.admins:
                        self.bot.admins.append(user_id)
                    # Notify the user
                    try:
                        self.bot.send_message(user_id, "You have been promoted to admin!, try /help to see your commands")
                    except Exception as e:
                        logger.error(f"Failed to notify promoted admin: {e}")
                self.bot.send_message(message.chat.id, f"✅ Promoted user {user_id} to {new_role}.")
            else:
                self.bot.send_message(message.chat.id, f"Failed to promote user {user_id} to {new_role}.")
        except Exception as e:
            self.bot.send_message(message.chat.id, f"Error: {e}")

    def _cmd_create_poll(self, message) -> None:
        """
        Create a poll in group chats. Usage (private chat only):
        /create_poll [group1,group2,...|all] <question> | <option1> | <option2> ...
        """
        if message.chat.type != "private":
            self.bot.send_message(message.chat.id, "Polls can only be created from private chat.")
            return
        parts = (message.text or "").split(" ", 2)
        if len(parts) < 3 or "|" not in parts[2]:
            self.bot.send_message(message.chat.id, "Usage: /create_poll [group1,group2,...|all] <question> | <option1> | <option2> ...")
            return
        target_groups_raw = parts[1].strip()
        poll_parts = [p.strip() for p in parts[2].split("|")]
        question = poll_parts[0]
        options = poll_parts[1:]
        if len(options) < 2:
            self.bot.send_message(message.chat.id, "A poll must have at least two options.")
            return

        # Get all group chats
        all_groups = [c for c in self.bot.db.get_all_chats() if c["chat_type"] in ["group", "supergroup"]]
        group_name_map = {c.get("username", str(c["chat_id"])): c["chat_id"] for c in all_groups}
        if target_groups_raw.lower() == "all":
            target_group_ids = [c["chat_id"] for c in all_groups]
            target_group_names = [c.get("username", str(c["chat_id"])) for c in all_groups]
        else:
            requested_names = [g.strip() for g in target_groups_raw.split(",")]
            target_group_ids = [group_name_map.get(name) for name in requested_names if group_name_map.get(name)]
            target_group_names = requested_names
        if not target_group_ids:
            self.bot.send_message(message.chat.id, "No valid target groups found.")
            return

        # Send poll to each group
        sent_groups = []
        for gid in target_group_ids:
            try:
                self.bot.bot.send_poll(
                    gid,
                    question,
                    options,
                    is_anonymous=True
                )
                sent_groups.append(gid)
            except Exception as e:
                logger.error(f"Failed to send poll to group {gid}: {e}")

        # Confirmation to superadmins
        from datetime import datetime
        tz_name = self.bot.admin_tools.settings_manager.get("timezone") or "UTC"
        try:
            import pytz
            tz = pytz.timezone(tz_name)
        except Exception:
            tz = None
        now = datetime.now(tz) if tz else datetime.utcnow()
        time_str = now.strftime("%Y-%m-%d %H:%M %Z")
        admin_name = getattr(message.from_user, "username", str(message.from_user.id))
        superadmin_ids = self.bot.db.get_users_by_role("superadmin")
        confirm_text = (
            f"✅ Poll created by admin @{admin_name} at {time_str}\n"
            f"Question: {question}\n"
            f"Sent to groups: {', '.join(target_group_names)}"
        )
        for sid in superadmin_ids:
            try:
                self.bot.send_message(sid, confirm_text)
            except Exception as e:
                logger.error(f"Failed to notify superadmin {sid}: {e}")
        self.bot.send_message(message.chat.id, f"Poll sent to {len(sent_groups)} group(s).")
    def _cmd_demote_user(self, message) -> None:
        """Demote a user to a lower role. Usage: /demote_user <user_id>"""
        parts = (message.text or "").split()
        if len(parts) < 2:
            self.bot.send_message(message.chat.id, "Usage: /demote_user <user_id>")
            return
        try:
            user_id = int(parts[1])
            ok = self.user_manager.demote_user(user_id, by_user_id=message.from_user.id)
            if ok:
                # Remove from admins list if role is now 'user'
                new_role = self.access_control.role_manager.get_role(user_id)
                if new_role == "user" and hasattr(self.bot, "admins"):
                    try:
                        self.bot.admins.remove(user_id)
                    except ValueError:
                        pass
                self.bot.send_message(message.chat.id, f"✅ Demoted user {user_id}.")
            else:
                self.bot.send_message(message.chat.id, f"Failed to demote user {user_id}.")
        except Exception as e:
            self.bot.send_message(message.chat.id, f"Error: {e}")

    def register_command(self, command: str, handler_func: Callable, required_role: str = "user"):
        """
        Register a new command with its handler and required role.
        
        Args:
            command: Command name without / prefix
            handler_func: Callback function(message) to handle command
            required_role: Minimum role required to use command
        """
        self.command_registry[command] = {
            'handler': handler_func,
            'role': required_role
        }
        logger.debug(f"Registered command /{command} requiring role: {required_role}")

    def handle_message(self, message) -> None:
        """
        Main message routing: if command, use command logic; if not, route to LLM if active, else ignore.
        """
        import re
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

    def _create_plugin_command_handler(self, plugin_name):
        """Create a command handler for a specific plugin."""
        def handler(message):
            self._handle_plugin_command(message, plugin_name)
        return handler

    def _handle_plugin_command(self, message, plugin_name):
        """Handle plugin commands and route to the correct plugin."""
        import logging
        logger = logging.getLogger(f"{plugin_name}_plugin_command")
        logger.info(f"Received {plugin_name} plugin command: {message.text}")
        
        if hasattr(self.bot, "plugins") and plugin_name in self.bot.plugins:
            plugin = self.bot.plugins[plugin_name]
            logger.info(f"{plugin_name.capitalize()} plugin active: {plugin.is_active()}")
            
            if plugin.is_active():
                parts = (message.text or "").split()
                cmd = parts[0][1:].lower()
                args = parts[1:]
                user_id = message.from_user.id
                user_role = self.access_control.role_manager.get_role(user_id)
                logger.info(f"Routing command '{cmd}' with args {args} from user {user_id} (role: {user_role})")
                
                reply = plugin.handle_command(cmd, args, user_id, user_role)
                logger.info(f"{plugin_name.capitalize()} plugin reply: {reply}")
                
                if reply:
                    self.bot.send_message(message.chat.id, reply, parse_mode="Markdown")
            else:
                logger.warning(f"{plugin_name.capitalize()} plugin is not active.")
        else:
            logger.warning(f"{plugin_name.capitalize()} plugin not found in bot.plugins.")

    def _handle_llm_plugin_command(self, message):
        """Handle LLM plugin commands if active. (Legacy - kept for compatibility)"""
        self._handle_plugin_command(message, "llm")

    def _handle_command(self, message) -> None:
        """Process commands with role checking."""
        parts = (message.text or "").split()
        if not parts:
            return

        command = parts[0][1:].lower()  # Remove / and normalize
        if '@' in command:  # Handle commands like /help@botname
            command = command.split('@')[0]

        if command not in self.command_registry:
            import logging
            logger = logging.getLogger("llm_plugin_command")
            logger.warning(f"Command '{command}' not found in registry. Registered commands: {list(self.command_registry.keys())}")
            return

        # Check permissions
        user_id = message.from_user.id
        required_role = self.command_registry[command]['role']
        
        # Skip permission check if command has no role requirement
        if required_role is not None and not self.access_control.has_role(user_id, required_role):
            logger.warning(f"Access denied: {user_id} tried /{command} needing {required_role}")
            self.bot.send_message(
                message.chat.id,
                "🚫 You don't have permission to use this command."
            )
            return

        # Execute handler
        try:
            handler = self.command_registry[command]['handler']
            handler(message)
        except Exception as e:
            logger.error(f"Error in command /{command}: {e}", exc_info=True)
            self._send_error_message(message.chat.id)

    def _handle_private_chat(self, message) -> None:
        """Handle direct messages to bot."""
        # If LLM plugin is active, respond to non-command messages as human-like
        text = message.text or ""
        if hasattr(self.bot, "plugins") and "llm" in self.bot.plugins:
            llm_plugin = self.bot.plugins["llm"]
            if llm_plugin.is_active():
                reply = llm_plugin.respond_to_message(message.from_user.id, text)
                self.bot.send_message(message.chat.id, reply)
                return
        # ...existing code...

    def _handle_group_message(self, message) -> None:
        """Handle messages in groups (when not mentioned)."""
        text = message.text or ""
        mentioned = self.bot.username and f"@{self.bot.username}" in text
        replied_to_bot = getattr(message, "reply_to_message", None) and getattr(message.reply_to_message.from_user, "username", None) == self.bot.username
        if hasattr(self.bot, "plugins") and "llm" in self.bot.plugins:
            llm_plugin = self.bot.plugins["llm"]
            if llm_plugin.is_active() and (mentioned or replied_to_bot):
                reply = llm_plugin.respond_to_message(message.from_user.id, text)
                self.bot.send_message(message.chat.id, reply)
                return
        # ...existing code...

    def _handle_group_mention(self, message) -> None:
        """Handle when bot is @mentioned in groups."""
        text = message.text or ""
        if hasattr(self.bot, "plugins") and "llm" in self.bot.plugins:
            llm_plugin = self.bot.plugins["llm"]
            if llm_plugin.is_active():
                reply = llm_plugin.respond_to_message(message.from_user.id, text)
                self.bot.send_message(message.chat.id, reply)
                return
        # ...existing code...

    # Built-in command handlers
    def _cmd_start(self, message) -> None:
        """Handle /start command."""
        username = getattr(message.from_user, 'first_name', None)
        if username:
            welcome_text = f"👋 Welcome {username}! Use /help to see available commands."
        else:
            welcome_text = "👋 Welcome! Use /help to see available commands."
        self.bot.send_message(
            message.chat.id,
            welcome_text
        )

    def _cmd_help(self, message) -> None:
        """Handle /help command."""
        user_id = message.from_user.id
        role_hierarchy = ["user", "admin", "superadmin"]
        user_role = self.access_control.role_manager.get_role(user_id) or "user"
        try:
            user_level = role_hierarchy.index(user_role)
        except ValueError:
            user_level = 0

        user_cmds = ["start", "help", "info", "stop"]
        admin_cmds = ["broadcast", "schedule_message", "list_scheduled", "cancel_scheduled", "settings", "set"]
        superadmin_cmds = ["promote_user", "demote_user"]
        command_descriptions = {
            "start": "/start - Start interaction",
            "help": "/help - Show this help message",
            "info": "/info - Bot info",
            "stop": "/stop - Stop the bot from replying",
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

        if hasattr(self.bot, "plugins"):
            for pname, plugin in self.bot.plugins.items():
                if plugin.is_active() and hasattr(plugin, "commands"):
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

    def _cmd_info(self, message) -> None:
        """Handle /info command."""
        # Show bot info, not user info
        bot_username = getattr(self.bot, 'username', None) or "Bot"
        tz = None
        lang = None
        admin_count = 0
        # Try to get timezone, language, admin count from bot core if available
        try:
            tz = getattr(getattr(self.bot, 'admin_tools', None), 'settings_manager', None)
            if tz:
                tz = tz.get('timezone')
                lang = tz.get('language')
            admin_count = len(getattr(self.bot, 'admins', []))
        except Exception:
            pass
        info_text = (
            f"🤖 Bot: @{bot_username}\n"
            f"🌍 Timezone: {tz or 'Africa/Cairo'}\n"
            f"🌐 Language: {lang or 'en'}\n"
        )
        self.bot.send_message(message.chat.id, info_text)

    def _send_error_message(self, chat_id: int) -> None:
        """Send a generic error message."""
        self.bot.send_message(
            chat_id,
            "⚠️ Sorry, something went wrong processing that request."
        )