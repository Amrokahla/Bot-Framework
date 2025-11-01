import importlib
import os
import json
from typing import Dict, List, Optional, Any
from core.plugins.plugin_base import BasePlugin


class PluginManager:
    def __init__(self, bot):
        """
        Args:
            bot: The main Telegram bot instance.
        """
        self.bot = bot
        self.plugins: Dict[str, BasePlugin] = {}
        self.available_plugins: Dict[str, type] = {}
        self.discover_plugins()

    # Removed config file logic; plugin activation is now managed programmatically

    def discover_plugins(self):
        """Scan the `plugins` directory and find available plugin classes."""
        plugins_dir = os.path.join(os.path.dirname(__file__), "..", "..", "plugins")
        if not os.path.exists(plugins_dir):
            os.makedirs(plugins_dir)

        for entry in os.listdir(plugins_dir):
            path = os.path.join(plugins_dir, entry)
            if os.path.isdir(path) and os.path.exists(os.path.join(path, "__init__.py")):
                # Try plugin.py first, fallback to main.py
                module_name = None
                if os.path.exists(os.path.join(path, "plugin.py")):
                    module_name = f"plugins.{entry}.plugin"
                elif os.path.exists(os.path.join(path, "main.py")):
                    module_name = f"plugins.{entry}.main"
                if module_name:
                    try:
                        module = importlib.import_module(module_name)
                        for attr in dir(module):
                            obj = getattr(module, attr)
                            if isinstance(obj, type) and issubclass(obj, BasePlugin) and obj is not BasePlugin:
                                instance = obj(self.bot)
                                self.available_plugins[instance.name()] = obj
                    except Exception as e:
                        print(f"⚠️ Failed to load plugin '{entry}': {e}")

    def activate_plugin(self, name: str):
        """Activate a specific plugin."""
        if name not in self.available_plugins:
            return f"❌ Plugin '{name}' not found."

        if name in self.plugins:
            return f"⚠️ Plugin '{name}' is already active."

        cls = self.available_plugins[name]
        plugin = cls(self.bot)
        plugin.activate()
        self.plugins[name] = plugin

        # Register plugin commands with MessageHandler if available
        if hasattr(self.bot, "message_handler") and hasattr(self.bot.message_handler, "add_plugin_commands"):
            self.bot.message_handler.add_plugin_commands(plugin)

        # No config file update; activation is managed in main.py or by client config

        return f"✅ Plugin '{name}' activated."

    def deactivate_plugin(self, name: str):
        """Deactivate a plugin."""
        if name not in self.plugins:
            return f"⚠️ Plugin '{name}' is not active."

        plugin = self.plugins.pop(name)
        plugin.deactivate()

        # No config file update; deactivation is managed in main.py or by client config

        return f"🚫 Plugin '{name}' deactivated."

    def handle_command(self, command: str, args: List[str], user_id: int) -> Optional[str]:
        """
        Route a command to the appropriate active plugin.
        """
        plugin_name = command.split("_")[0]  # e.g. "llm_info" → "llm"
        if plugin_name not in self.plugins:
            return f"❌ This bot doesn’t support the '{plugin_name}' plugin. Contact admin to enable it."

        plugin = self.plugins[plugin_name]
        if not plugin.is_active():
            return f"⚠️ Plugin '{plugin_name}' is not active."

        try:
            return plugin.handle_command(command, args, user_id)
        except Exception as e:
            return f"⚠️ Error in plugin '{plugin_name}': {e}"

    def list_active_plugins(self) -> List[str]:
        return list(self.plugins.keys())

    def list_available_plugins(self) -> List[str]:
        return list(self.available_plugins.keys())

    def get_help(self) -> str:
        """Generate combined help text for all active plugins."""
        if not self.plugins:
            return "No plugins are currently active."
        lines = ["🤖 *Active Plugins:*"]
        for name, plugin in self.plugins.items():
            lines.append(plugin.help_text())
            lines.append("")  # space between plugins
        return "\n".join(lines)
