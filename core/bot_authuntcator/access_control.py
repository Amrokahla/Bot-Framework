import functools
import logging
from core.bot_authuntcator.role_manager import RoleManager

logger = logging.getLogger(__name__)


class AccessControl:
    """Handles permission checks and role-based access decorators."""

    def __init__(self, db):
        self.role_manager = RoleManager(db)

    def has_role(self, user_id: int, required_role: str) -> bool:
        """Check if user has the required role or higher."""
        # Match role_manager.py hierarchy
        hierarchy = ["user", "moderator", "admin", "superadmin"]
        user_role = self.role_manager.get_role(user_id) or "user"
        try:
            return hierarchy.index(user_role) >= hierarchy.index(required_role)
        except ValueError:
            return False

    def require_role(self, required_role: str):
        """Decorator to protect command handlers by role."""

        def decorator(func):
            @functools.wraps(func)
            def wrapper(bot, message, *args, **kwargs):
                user_id = message.from_user.id
                if not self.has_role(user_id, required_role):
                    logger.warning(f"Access denied for {user_id}, needs {required_role}")
                    bot.send_message(message.chat.id, "🚫 You don't have permission for this command.")
                    return
                return func(bot, message, *args, **kwargs)

            return wrapper

        return decorator
