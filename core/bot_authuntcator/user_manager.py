import logging
from typing import Dict, Optional, List
from core.database.database_manager import DatabaseManager
from core.bot_authuntcator.role_manager import RoleManager

logger = logging.getLogger(__name__)

class UserManager:
    """
    Manages user tracking, roles, and metadata.
    Provides a unified interface for user operations.
    """

    def __init__(self, db: DatabaseManager, role_manager: RoleManager):
        self.db = db
        self.role_manager = role_manager
        self._ensure_default_roles()

    def _ensure_default_roles(self) -> None:
        """Ensure critical roles exist for first-time setup."""
        superadmins = self.role_manager.get_users_by_role("superadmin")
        if not superadmins:
            logger.warning("No superadmin found in system. Use set_role() to assign one.")

    def add_user(self, user_id: int, username: Optional[str], chat_type: str = "private") -> None:
        """
        Add or update a user in the system.
        
        Args:
            user_id: Telegram user ID
            username: Optional Telegram username
            chat_type: Type of chat ("private", "group", etc)
        """
        # Ensure user exists in DB
        self.db.ensure_user_exists(user_id, username, chat_type)
        
        # Assign default role if none exists
        if not self.role_manager.get_role(user_id):
            self.role_manager.set_role(user_id, "user")
            logger.debug(f"Assigned default role 'user' to {user_id}")

    def get_user_info(self, user_id: int) -> Dict:
        """
        Get comprehensive user information.
        
        Returns:
            Dict with user details including role and metadata
        """
        role = self.role_manager.get_role(user_id)
        # Extend with more user data as needed
        return {
            'user_id': user_id,
            'role': role,
            'is_admin': role in ('admin', 'superadmin'),
            'is_blocked': self.is_blocked(user_id)
        }

    def set_blocked_status(self, user_id: int, blocked: bool = True) -> None:
        """Block or unblock a user."""
        self.db.set_user_blocked(user_id, blocked)
        logger.info(f"User {user_id} {'blocked' if blocked else 'unblocked'}")

    def is_blocked(self, user_id: int) -> bool:
        """Check if a user is blocked."""
        return self.db.is_user_blocked(user_id)

    def get_users_by_role(self, role: str) -> List[int]:
        """Get all user IDs with a specific role."""
        return self.role_manager.get_users_by_role(role)

    def promote_user(self, user_id: int, new_role: str, by_user_id: Optional[int] = None) -> bool:
        """
        Promote a user to a new role.
        
        Args:
            user_id: User to promote
            new_role: Target role
            by_user_id: ID of user performing promotion (for permission check)
            
        Returns:
            bool: True if promotion successful
        """
        return self.role_manager.promote_user(user_id, new_role, by_user_id)

    def demote_user(self, user_id: int, by_user_id: Optional[int] = None) -> bool:
        """
        Demote a user down one role level.
        
        Args:
            user_id: User to demote
            by_user_id: ID of user performing demotion (for permission check)
            
        Returns:
            bool: True if demotion successful
        """
        return self.role_manager.demote_user(user_id, by_user_id)

    def get_all_users(self) -> List[Dict]:
        """
        Get list of all users with their roles.
        
        Returns:
            List of user info dicts
        """
        users = []
        for user in self.db.get_all_users():
            user_id = user['chat_id']  # chat_id is user_id for private chats
            users.append({
                'user_id': user_id,
                'username': user['username'],
                'role': self.role_manager.get_role(user_id),
                'first_seen': user['first_seen']
            })
        return users