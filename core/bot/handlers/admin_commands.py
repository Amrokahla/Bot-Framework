"""
Admin and superadmin command handlers.
"""
import logging

logger = logging.getLogger(__name__)


class AdminCommands:
    """Handlers for admin and superadmin commands."""

    def __init__(self, bot, user_manager, access_control):
        self.bot = bot
        self.user_manager = user_manager
        self.access_control = access_control

    def handle_promote_user(self, message) -> None:
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

    def handle_demote_user(self, message) -> None:
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

    def handle_create_poll(self, message) -> None:
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
