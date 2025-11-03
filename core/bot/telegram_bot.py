import logging
import re
from collections import defaultdict, deque
import telebot
from core.config.config import get_settings
from core.bot_authuntcator.admin_tools import AdminTools
from core.database.database_manager import DatabaseManager

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class TelegramBot:
    def __init__(self, settings=None):
        # Load config
        self.settings = settings or get_settings()
        self.bot = telebot.TeleBot(self.settings.bot_token)
        self.username = self.bot.get_me().username

        # Database manager for this bot instance
        self.db = DatabaseManager(bot_id=self.username)
        logger.info(f"Database loaded for bot {self.username}")

        # Load admins from DB roles; if none exist, persist admin IDs from settings
        db_admins = self.db.get_users_by_role("admin") or []
        
        # Ensure first admin from settings becomes superadmin
        if self.settings.admin_ids:
            first_admin = int(self.settings.admin_ids[0])
            try:
                self.db.add_role(first_admin, "superadmin")
                logger.info(f"Set first admin {first_admin} as superadmin")
                
                # Set remaining admins
                for a in self.settings.admin_ids[1:]:
                    try:
                        self.db.add_role(int(a), "admin")
                    except Exception:
                        logger.warning(f"Failed to add admin role for id: {a}")
            except Exception as e:
                logger.error(f"Failed to set superadmin: {e}")
                
        # Get final admin list including newly added ones
        db_admins = self.db.get_users_by_role("admin") or []
        superadmins = self.db.get_users_by_role("superadmin") or []
        self.admins = list(set(db_admins + superadmins + [int(a) for a in self.settings.admin_ids]))
        self.blocked_users = set()

        # Message caches
        self.message_history = defaultdict(lambda: deque(maxlen=20))
        self.user_states = defaultdict(dict)

        # Initialize core components
        from core.bot_authuntcator.access_control import AccessControl
        from core.bot_authuntcator.user_manager import UserManager
        from core.bot.handlers import MessageHandler
        from core.bot_authuntcator.role_manager import RoleManager
        from core.plugins.plugin_manager import PluginManager

        # Initialize components in order of dependency
        self.role_manager = RoleManager(self.db)
        self.access_control = AccessControl(self.db)
        self.user_manager = UserManager(self.db, self.role_manager)

        # Initialize admin tools (needs to be before message handler for command registration)
        self.admin_tools = AdminTools(self, self.admins, self.db)

        # Initialize PluginManager
        self.plugin_manager = PluginManager(self)

        # Activate plugins before MessageHandler is constructed
        # (Assume active_plugins is set from config or elsewhere)
        if hasattr(self, "active_plugins"):
            for pname in self.active_plugins:
                if pname in self.plugin_manager.available_plugins:
                    self.plugin_manager.activate_plugin(pname)
                    logger.info(f"✅ Plugin '{pname}' activated via PluginManager.")
                else:
                    logger.warning(f"Plugin '{pname}' not found in available plugins.")

        # Populate self.plugins for routing
        self.plugins = dict(self.plugin_manager.plugins)

        # Initialize message handler and register core admin commands
        self.message_handler = MessageHandler(self, self.user_manager, self.access_control)
        self._register_admin_commands()
        # Register all plugin commands after both plugin activation and MessageHandler construction
        self.message_handler.register_all_plugin_commands()

        # Ensure default timezone is Cairo if not set
        try:
            if not self.admin_tools.settings_manager.get("timezone"):
                self.admin_tools.settings_manager.set("timezone", "Africa/Cairo")
        except Exception as e:
            logger.warning(f"Could not enforce timezone setting: {e}")

        logger.info(f"Telegram Bot initialized as @{self.username}")
        self._register_basic_handlers()
        logger.info("✅ Message routing, admin tools, and plugins initialized")

    # --- Handler registration ---
    def register_handler(self, handler_function, **filters):
        self._register_handler(handler_function, **filters)

    def _register_admin_commands(self):
        """Register built-in admin commands with appropriate roles."""
        self.message_handler.register_command("broadcast", self.admin_tools._broadcast_handler, "admin")
        self.message_handler.register_command("schedule_message", self.admin_tools._schedule_handler, "admin")
        self.message_handler.register_command("list_scheduled", self.admin_tools._list_scheduled_handler, "admin")
        self.message_handler.register_command("cancel_scheduled", self.admin_tools._cancel_scheduled_handler, "admin")
        self.message_handler.register_command("settings", self.admin_tools.show_settings, "admin")
        self.message_handler.register_command("set", self.admin_tools.set_setting, "admin")

    def _register_basic_handlers(self):
        """Register core message handler to process all messages."""
        @self.bot.message_handler(func=lambda _: True, content_types=['text', 'audio', 'document', 'photo', 'sticker', 'video', 'voice'])
        def handle_all_messages(message):
            if hasattr(self, 'message_handler'):
                self.message_handler.handle_message(message)
            else:
                # Fallback to basic handlers if message_handler not yet set
                if message.content_type == 'text':
                    text = message.text or ""
                    if text.startswith('/help') or text.startswith('/start'):
                        self._help_handler(message)
                    elif text.startswith('/info'):
                        self._info_handler(message)
                else:
                    self._default_media_handler(message)

    def _register_handler(self, handler_function, **filters):
        @self.bot.message_handler(**filters)
        def wrapper(message):
            user_id = message.from_user.id
            chat_id = message.chat.id
            chat_type = message.chat.type
            text = message.text or ""

            # --- Save chat/user info persistently ---
            self.db.ensure_user_exists(user_id, message.from_user.username)
            self.db.ensure_chat_exists(chat_id, chat_type)

            # --- Handle blocked users ---
            if user_id in self.blocked_users:
                return  # Silently ignore blocked users

            # --- Private messages ---
            if chat_type == "private":
                self._store_message(chat_id, message)
                return handler_function(message)

            # --- Group or supergroup ---
            if chat_type in ["group", "supergroup"]:
                if not text and not getattr(message, "reply_to_message", None):
                    return
                if self._is_mentioned(message) or self._is_reply_to_bot(message):
                    message.text = self._strip_mention(message.text or "")
                    self._store_message(chat_id, message)

                    # Delegate admin commands
                    if message.text.startswith("/"):
                        is_admin = self.db.is_role(user_id, "admin") or user_id in self.admins
                        if not is_admin:
                            return
                            
                        cmd = message.text.split()[0]
                        if cmd == "/schedule_message":
                            return self.admin_tools._schedule_handler(message)
                        if cmd == "/list_scheduled":
                            return self.admin_tools._list_scheduled_handler(message)
                        if cmd == "/cancel_scheduled":
                            return self.admin_tools._cancel_scheduled_handler(message)
                        if cmd == "/broadcast":
                            return self.admin_tools._broadcast_handler(message)
                        if cmd == "/settings":
                            return self.admin_tools.show_settings(message)
                        if cmd == "/set":
                            return self.admin_tools.set_setting(message)

                    return handler_function(message)
        return wrapper

    # --- Handlers ---
    def _help_handler(self, message):
        user_id = message.from_user.id
        is_admin = self.db.is_role(user_id, "admin") or user_id in self.admins
        is_private = message.chat.type == "private"

        help_lines = [
            "/start - Start interaction",
            "/help - Show this help message",
            "/info - Bot info",
            "/stop - Stop the bot from replying"
        ]

        if is_admin:
            help_lines += [
                "",
                "Admin commands:",
                "/schedule_message",
                "/list_scheduled",
                "/cancel_scheduled",
                "/broadcast",
                "/settings",
                "/set"
            ]

        help_text = "\n".join(help_lines)
        if not is_private and is_admin:
            try:
                self.send_message(user_id, help_text)
                self.send_message(message.chat.id, "Sent admin help privately.")
            except Exception as e:
                logger.error(f"Failed to DM admin help: {e}")
                self.send_message(message.chat.id, "Could not send admin help DM.")
        else:
            self.send_message(message.chat.id, help_text)

    def _info_handler(self, message):
        tz = self.admin_tools.settings_manager.get("timezone") or "Africa/Cairo"
        lang = self.admin_tools.settings_manager.get("language") or "en"
        self.send_message(message.chat.id,
                          f"🤖 Bot: @{self.username}\n🌍 Timezone: {tz}\n🌐 Language: {lang}\n👮 Admins: {len(self.admins)}")

    def _default_media_handler(self, message):
        return self.send_message(message.chat.id, "This bot doesn’t handle media yet.")

    # --- Helpers ---
    def _is_mentioned(self, message):
        if not getattr(message, "entities", None):
            return False
        for e in message.entities:
            if e.type == "mention":
                mention = message.text[e.offset:e.offset + e.length]
                if mention.lower() == f"@{self.username.lower()}":
                    return True
        return False

    def _is_reply_to_bot(self, message):
        return getattr(message, "reply_to_message", None) and \
               getattr(message.reply_to_message.from_user, "username", None) == self.username

    def _strip_mention(self, text):
        return re.sub(fr"@{self.username}\b", "", text or "", flags=re.IGNORECASE).strip()

    def _store_message(self, chat_id, message):
        self.message_history[chat_id].append(message)
        self.db.save_message(chat_id, message.from_user.id, message.text or "")

    # --- Messaging ---
    def send_message(self, chat_id, text, **kwargs):
        try:
            self.bot.send_message(chat_id, text, **kwargs)
        except Exception as e:
            logger.warning(f"Send error: {e}")
            try:
                self.bot.send_message(chat_id, text)
            except Exception:
                logger.error("Failed to send message fallback.")

    # --- Lifecycle ---
    def start_polling(self):
        logger.info("Starting polling...")
        self.bot.infinity_polling()

    def stop(self):
        logger.info("Stopping...")
        try:
            self.admin_tools.stop()
        except Exception:
            pass
        logger.info("Stopped.")
