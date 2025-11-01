import logging
from core.database.database_manager import DatabaseManager

logger = logging.getLogger(__name__)


class RoleManager:
    """
    Manages user roles (superadmin, admin, moderator, user) for the bot.
    Uses DatabaseManager as persistent storage.
    """

    ROLE_HIERARCHY = ["user", "admin", "superadmin"]

    def __init__(self, db: DatabaseManager):
        self.db = db
        self._ensure_superadmin_exists()

    # -------------------------------------------------------------------------
    # Initialization
    # -------------------------------------------------------------------------
    def _ensure_superadmin_exists(self):
        """
        Ensures there is always at least one superadmin.
        (Useful if the bot restarts or database resets.)
        """
        superadmins = self.db.get_users_by_role("superadmin")
        if not superadmins:
            logger.warning("⚠️ No superadmin found. You must assign one manually using promote_user().")

    # -------------------------------------------------------------------------
    # Role Queries
    # -------------------------------------------------------------------------
    def get_role(self, user_id: int) -> str:
        """Return the role name for a user. Defaults to 'user'."""
        roles = self.db.get_roles()
        for r in roles:
            if r["user_id"] == user_id:
                return r["role"]
        return "user"

    def has_role(self, user_id: int, role: str) -> bool:
        """Check if a user holds (or outranks) the given role."""
        current = self.get_role(user_id)
        return self._compare_roles(current, role) >= 0

    # -------------------------------------------------------------------------
    # Role Management
    # -------------------------------------------------------------------------
    def promote_user(self, target_id: int, new_role: str, by_user: int | None = None) -> bool:
        """
        Promote a user to a higher role.
        Only allowed if the acting user outranks the target role.
        """
        if new_role not in self.ROLE_HIERARCHY:
            logger.error(f"Invalid role: {new_role}")
            return False

        # Check permission if someone initiated this
        if by_user is not None:
            actor_role = self.get_role(by_user)
            if self._compare_roles(actor_role, new_role) <= 0:
                logger.warning(f"User {by_user} ({actor_role}) not authorized to promote to {new_role}.")
                return False

        self.db.add_role(target_id, new_role)
        logger.info(f"✅ User {target_id} promoted to {new_role}.")
        return True

    def demote_user(self, target_id: int, by_user: int | None = None) -> bool:
        """
        Demote a user by one level.
        Superadmins cannot be demoted by anyone below them.
        """
        current_role = self.get_role(target_id)
        if current_role == "user":
            logger.info(f"User {target_id} is already at lowest role.")
            return False

        # Permission check
        if by_user is not None:
            actor_role = self.get_role(by_user)
            if self._compare_roles(actor_role, current_role) <= 0:
                logger.warning(f"User {by_user} ({actor_role}) not authorized to demote {target_id} ({current_role}).")
                return False

        # Demote by one step
        idx = self.ROLE_HIERARCHY.index(current_role)
        new_role = self.ROLE_HIERARCHY[idx - 1]
        self.db.add_role(target_id, new_role)
        logger.info(f"⬇️ User {target_id} demoted from {current_role} to {new_role}.")
        return True

    def set_role(self, target_id: int, role: str):
        """Force-assign a role (useful for migrations or fixes)."""
        if role not in self.ROLE_HIERARCHY:
            raise ValueError(f"Invalid role: {role}")
        self.db.add_role(target_id, role)
        logger.info(f"⚙️ Role manually set: {target_id} → {role}")

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------
    def get_users_by_role(self, role: str) -> list[int]:
        """Get list of user IDs that have a specific role."""
        return self.db.get_users_by_role(role)

    def _compare_roles(self, r1: str, r2: str) -> int:
        """
        Compare two roles:
        > 0 means r1 outranks r2
        = 0 means same
        < 0 means lower
        """
        try:
            return self.ROLE_HIERARCHY.index(r1) - self.ROLE_HIERARCHY.index(r2)
        except ValueError:
            return -999

    def list_all_roles(self):
        """Return all users and their roles."""
        roles = self.db.get_roles()
        return {r["user_id"]: r["role"] for r in roles}
