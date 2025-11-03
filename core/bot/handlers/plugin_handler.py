"""
Plugin command handling and routing.
"""
import logging

logger = logging.getLogger(__name__)


class PluginHandler:
    """Handles plugin command routing and access control."""

    def __init__(self, bot, access_control):
        self.bot = bot
        self.access_control = access_control

    def get_minimum_role(self, allowed_roles):
        """
        Determine the minimum role required based on allowed_roles list.
        
        Args:
            allowed_roles: List of allowed roles (e.g., ["admin", "superadmin"] or ["all"])
            
        Returns:
            str or None: Minimum role required (None means no restriction)
        """
        if not allowed_roles:
            return "admin"  # Default to admin if not specified
        
        # If "all" is in allowed_roles, no role restriction
        if "all" in allowed_roles:
            return None
        
        # Role hierarchy: superadmin > admin > user
        role_hierarchy = {"user": 1, "admin": 2, "superadmin": 3}
        
        # Find the lowest role in the hierarchy
        min_level = float('inf')
        min_role = "admin"
        
        for role in allowed_roles:
            role_lower = role.lower()
            if role_lower in role_hierarchy:
                level = role_hierarchy[role_lower]
                if level < min_level:
                    min_level = level
                    min_role = role_lower
        
        return min_role

    def check_plugin_access(self, user_role, allowed_roles):
        """
        Check if user_role is allowed based on allowed_roles list.
        
        Args:
            user_role: User's current role (e.g., "user", "admin", "superadmin")
            allowed_roles: List of allowed roles for the plugin
            
        Returns:
            bool: True if user has access, False otherwise
        """
        if not allowed_roles:
            return False
        
        # If "all" is in allowed_roles, everyone has access
        if "all" in allowed_roles:
            return True
        
        # Role hierarchy: superadmin > admin > user
        role_hierarchy = {"user": 1, "admin": 2, "superadmin": 3}
        
        user_level = role_hierarchy.get(user_role, 0)
        
        # Check if user's role is in allowed_roles or higher
        for allowed_role in allowed_roles:
            allowed_level = role_hierarchy.get(allowed_role.lower(), 0)
            if user_level >= allowed_level:
                return True
        
        return False

    def create_plugin_command_handler(self, plugin_name):
        """Create a command handler for a specific plugin."""
        def handler(message):
            self.handle_plugin_command(message, plugin_name)
        return handler

    def handle_plugin_command(self, message, plugin_name):
        """Handle plugin commands and route to the correct plugin."""
        logger.info(f"Received {plugin_name} plugin command: {message.text}")
        
        # Generic security message - same for all unauthorized/invalid access
        security_message = "⚠️ This command either doesn't exist or you don't have permission to use it."
        
        if hasattr(self.bot, "plugins") and plugin_name in self.bot.plugins:
            plugin = self.bot.plugins[plugin_name]
            logger.info(f"{plugin_name.capitalize()} plugin active: {plugin.is_active()}")
            
            if plugin.is_active():
                parts = (message.text or "").split()
                cmd = parts[0][1:].lower()
                args = parts[1:]
                user_id = message.from_user.id
                user_role = self.access_control.role_manager.get_role(user_id)
                
                # Check if user has permission based on plugin's allowed_roles
                allowed_roles = getattr(plugin, "allowed_roles", ["admin", "superadmin"])
                if not self.check_plugin_access(user_role, allowed_roles):
                    logger.warning(f"User {user_id} (role: {user_role}) attempted to access {plugin_name} command but lacks permission")
                    # Use generic security message to avoid revealing command details
                    self.bot.send_message(message.chat.id, security_message)
                    return
                
                logger.info(f"Routing command '{cmd}' with args {args} from user {user_id} (role: {user_role})")
                
                try:
                    reply = plugin.handle_command(cmd, args, user_id, user_role)
                    logger.info(f"{plugin_name.capitalize()} plugin reply: {reply}")
                    
                    if reply:
                        try:
                            self.bot.send_message(message.chat.id, reply, parse_mode="Markdown")
                        except Exception as parse_error:
                            # If Markdown parsing fails, try without formatting
                            logger.warning(f"Markdown parse error, sending plain text: {parse_error}")
                            self.bot.send_message(message.chat.id, reply)
                except Exception as e:
                    logger.error(f"Error executing {plugin_name} command: {e}", exc_info=True)
                    self.bot.send_message(message.chat.id, "⚠️ An error occurred while processing your command.")
            else:
                logger.warning(f"{plugin_name.capitalize()} plugin is not active.")
                # Use generic message - don't reveal plugin state
                self.bot.send_message(message.chat.id, security_message)
        else:
            logger.warning(f"{plugin_name.capitalize()} plugin not found in bot.plugins.")
            # Use generic message - don't reveal plugin existence
            self.bot.send_message(message.chat.id, security_message)

    def register_plugin_commands(self, command_registry):
        """Register commands from all active plugins."""
        active_plugins = getattr(self.bot, "active_plugins", [])
        if hasattr(self.bot, "plugins"):
            for pname, plugin in self.bot.plugins.items():
                if pname in active_plugins and plugin.is_active() and hasattr(plugin, "commands"):
                    # Get allowed_roles from plugin config, default to admin
                    allowed_roles = getattr(plugin, "allowed_roles", ["admin", "superadmin"])
                    # Determine minimum role required
                    min_role = self.get_minimum_role(allowed_roles)
                    for cmd, desc in plugin.commands().items():
                        cmd_name = cmd.lstrip("/").lower()
                        # Create a handler that routes to the correct plugin
                        handler = self.create_plugin_command_handler(pname)
                        command_registry.register(cmd_name, handler, min_role)

    def add_plugin_commands(self, plugin, command_registry):
        """Register commands from a single plugin after activation."""
        if plugin.is_active() and hasattr(plugin, "commands"):
            plugin_name = plugin.name()
            # Get allowed_roles from plugin config, default to admin
            allowed_roles = getattr(plugin, "allowed_roles", ["admin", "superadmin"])
            # Determine minimum role required
            min_role = self.get_minimum_role(allowed_roles)
            for cmd, desc in plugin.commands().items():
                cmd_name = cmd.lstrip("/").lower()
                # Create a handler that routes to the correct plugin
                handler = self.create_plugin_command_handler(plugin_name)
                command_registry.register(cmd_name, handler, min_role)
