import logging
import threading
import time
import pytz
from datetime import datetime
from collections import deque

logger = logging.getLogger(__name__)


class AdminSettingsManager:
    DEFAULT_SETTINGS = {
        "language": "en",
        "timezone": "Africa/Cairo",
        "notifications": True,
        "default_target": "all",
        "time_format": "24h",
        "log_level": "info"
    }

    def __init__(self, db):
        """
        db: DatabaseManager instance
        """
        self.db = db
        self._lock = threading.Lock()

        # Initialize settings in DB if not present
        for key, val in self.DEFAULT_SETTINGS.items():
            if self.db.get_setting(key) is None:
                self.db.set_setting(key, val)

    def get(self, key):
        value = self.db.get_setting(key)
        if value is None:
            value = self.DEFAULT_SETTINGS.get(key)
            self.db.set_setting(key, value)
        return value

    def set(self, key, value):
        if key not in self.DEFAULT_SETTINGS:
            return False
        self.db.set_setting(key, value)
        logger.info(f"Updated setting: {key} = {value}")
        return True

    def get_all(self):
        settings = self.db.get_all_settings()
        merged = {**self.DEFAULT_SETTINGS, **settings}
        return merged


class AdminTools:
    def __init__(self, bot_core, admin_ids, db):
        """
        bot_core: TelegramBot instance
        admin_ids: list of admin IDs
        db: DatabaseManager instance
        """
        self.bot_core = bot_core
        self.telebot = getattr(bot_core, "bot", None) or bot_core
        self.admin_ids = admin_ids
        self.db = db
        self.lock = threading.Lock()
        self.running = True

        # Use DB-based settings manager
        self.settings_manager = AdminSettingsManager(self.db)

        # Start scheduler thread
        self.thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        self.thread.start()

        # Register admin commands
        self.bot_core.register_handler(self._schedule_handler, commands=['schedule_message'])
        self.bot_core.register_handler(self._list_scheduled_handler, commands=['list_scheduled'])
        self.bot_core.register_handler(self._cancel_scheduled_handler, commands=['cancel_scheduled'])
        self.bot_core.register_handler(self._broadcast_handler, commands=['broadcast'])
        self.bot_core.register_handler(self.show_settings, commands=['settings'])
        self.bot_core.register_handler(self.set_setting, commands=['set'])

        logger.info("AdminTools initialized with DB-backed persistence.")

    # ─────────────────────────────────────────────
    # Scheduling System
    # ─────────────────────────────────────────────
    def _scheduler_loop(self):
        """
        Background thread that checks for due scheduled messages in the DB
        and sends them to the appropriate targets.
        """
        while self.running:
            try:
                tz_name = self.settings_manager.get("timezone") or "Africa/Cairo"
                tz = pytz.timezone(tz_name)
                now = datetime.now(tz)

                due = self.db.get_due_scheduled_messages(now)
                for msg in due:
                    target = msg["target"]
                    text = msg["text"]
                    sent_count = 0

                    chat_ids = self.db.get_chats_by_type(target)
                    for chat_id in chat_ids:
                        try:
                            self.bot_core.send_message(chat_id, f"📅 Scheduled: {text}")
                            sent_count += 1
                        except Exception as e:
                            logger.error(f"Failed to send scheduled message to chat {chat_id}: {e}")

                    logger.info(f"Sent scheduled message to {sent_count} chats.")

                    self.db.mark_scheduled_as_sent(msg["id"])

            except Exception as e:
                logger.error(f"Scheduler error: {e}")

            time.sleep(30)

    # ─────────────────────────────────────────────
    # Command Handlers
    # ─────────────────────────────────────────────
    def _schedule_handler(self, message):
        if message.from_user.id not in self.admin_ids:
            return
        parts = (message.text or "").split(maxsplit=4)
        if len(parts) < 5:
            return self.bot_core.send_message(
                message.chat.id,
                "Usage: /schedule_message <target> <YYYY-MM-DD> <HH:MM> <message>\nTargets: individuals | groups | all"
            )

        _, target, date_str, time_str, text = parts
        if target not in ("individuals", "groups", "all"):
            return self.bot_core.send_message(message.chat.id, "Invalid target. Must be one of: individuals, groups, all.")

        try:
            tz = pytz.timezone(self.settings_manager.get("timezone"))
            send_time = tz.localize(datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M"))
            if send_time <= datetime.now(tz):
                return self.bot_core.send_message(message.chat.id, "Send time must be in the future.")
        except Exception:
            return self.bot_core.send_message(message.chat.id, "Invalid date/time format. Use: YYYY-MM-DD HH:MM (24h).")

        # Save to DB instead of memory
        self.db.add_scheduled_message(target, text, send_time)
        self.bot_core.send_message(
            message.chat.id,
            f"✅ Message scheduled for *{target}* at {send_time.strftime('%Y-%m-%d %H:%M')}.\nMessage: {text}",
            parse_mode="Markdown"
        )

    def _list_scheduled_handler(self, message):
        if message.from_user.id not in self.admin_ids:
            return
        scheduled = self.db.get_pending_scheduled_messages()
        if not scheduled:
            self.bot_core.send_message(message.chat.id, "No scheduled messages.")
            return
        lines = []
        for idx, m in enumerate(scheduled, start=1):
            # Use correct keys for scheduled message dict
            target = m.get('target_type', m.get('target', ''))
            send_time = m.get('send_time', '')
            text = m.get('message', m.get('text', ''))
            lines.append(f"{idx}. Target: {target} at {send_time} — {text[:60]}")
        self.bot_core.send_message(message.chat.id, "\n".join(lines))

    def _cancel_scheduled_handler(self, message):
        if message.from_user.id not in self.admin_ids:
            return
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            return self.bot_core.send_message(message.chat.id, "Usage: /cancel_scheduled <index|all>")
        arg = parts[1].strip()

        if arg.lower() == "all":
            self.db.clear_all_scheduled()
            return self.bot_core.send_message(message.chat.id, "All scheduled messages cancelled.")

        try:
            idx = int(arg) - 1
            pending = self.db.get_pending_scheduled_messages()
            if idx < 0 or idx >= len(pending):
                return self.bot_core.send_message(message.chat.id, "Index out of range.")
            self.db.delete_scheduled_message(pending[idx]["id"])
            self.bot_core.send_message(message.chat.id, f"Cancelled scheduled: {pending[idx]['text']}")
        except Exception as e:
            logger.error(f"Failed to cancel scheduled message: {e}")
            self.bot_core.send_message(message.chat.id, f"Error cancelling scheduled message: {e}")

    def _broadcast_handler(self, message):
        """Admin command: /broadcast <text> — send to all tracked chats and log recipients."""
        if message.from_user.id not in self.admin_ids:
            return
        parts = (message.text or "").split(maxsplit=1)
        if len(parts) < 2:
            return self.bot_core.send_message(message.chat.id, "Usage: /broadcast <message>")
        text = parts[1]

        chats = self.db.get_all_chats()
        sent, failed = 0, 0

        for chat in chats:
            try:
                self.bot_core.send_message(chat["chat_id"], f"📢 Broadcast:\n{text}")
                sent += 1
            except Exception as e:
                failed += 1
                logger.error(f"Failed to broadcast to {chat['chat_id']}: {e}")

        self.bot_core.send_message(message.chat.id, f"Broadcast complete. Sent: {sent}. Failed: {failed}.")

    # ─────────────────────────────────────────────
    # Settings Management
    # ─────────────────────────────────────────────
    def show_settings(self, message):
        if message.from_user.id not in self.admin_ids:
            return
        current = self.settings_manager.get_all()
        lines = [f"{k}: {v}" for k, v in current.items()]
        self.bot_core.send_message(message.chat.id, "Admin settings:\n" + "\n".join(lines))

    def set_setting(self, message):
        if message.from_user.id not in self.admin_ids:
            return
        parts = message.text.split(maxsplit=2)
        if len(parts) < 3:
            return self.bot_core.send_message(message.chat.id, "Usage: /set <key> <value>")
        key, value = parts[1], parts[2]
        if key == "timezone" and value not in pytz.all_timezones:
            return self.bot_core.send_message(message.chat.id, f"Invalid timezone: {value}")
        ok = self.settings_manager.set(key, value)
        if ok:
            self.bot_core.send_message(message.chat.id, f"Updated {key} -> {value}")
        else:
            self.bot_core.send_message(message.chat.id, f"Unknown setting: {key}")

    # ─────────────────────────────────────────────
    # Misc
    # ─────────────────────────────────────────────
    def stats(self):
        return {
            'blocked_users_count': len(self.bot_core.blocked_users),
            'total_users_tracked': self.db.count_users()
        }

    def stop(self):
        self.running = False
        logger.info("AdminTools scheduler stopped.")
