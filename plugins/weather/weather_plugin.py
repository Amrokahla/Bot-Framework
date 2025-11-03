"""
Weather Plugin for Telegram Bot - integrates weatherapi.com for weather information
"""

from core.plugins.plugin_base import BasePlugin
from .weather_api import WeatherAPI
import logging

logger = logging.getLogger("weather_plugin")

class WeatherPlugin(BasePlugin):
    def __init__(self, bot, config=None):
        super().__init__(bot)
        self.config = config or {}
        self.api_key = self.config.get("api_key")
        self.provider = self.config.get("provider", "weatherapi")
        self.weather_api = WeatherAPI(self.api_key, self.provider)
        self.active = False

    @staticmethod
    def name():
        return "weather"

    @staticmethod
    def description():
        return "Weather plugin for fetching current weather information from weatherapi.com"

    def commands(self):
        return {
            "/weather_info": "Show weather plugin provider info",
            "/weather": "Get current weather for a location (usage: /weather Cairo)"
        }

    def help_text(self):
        lines = [
            "🌤 *Weather Plugin*",
            "",
            "Commands:",
        ]
        for cmd, desc in self.commands().items():
            lines.append(f"• {cmd} — {desc}")
        return "\n".join(lines)

    def activate(self):
        if not self.api_key:
            print("⚠️ Weather API key not set in client config. Please configure it before activation.")
            return
        self.active = True
        print(f"✅ Weather Plugin activated with provider: {self.provider}")

    def deactivate(self):
        self.active = False
        print("🚫 Weather Plugin deactivated.")

    def is_active(self):
        return self.active

    def health_status(self):
        status = []
        if self.api_key:
            status.append("✅ API key set")
        else:
            status.append("❌ API key missing")
        if self.active:
            status.append("✅ Plugin active")
        else:
            status.append("❌ Plugin not active")
        return ", ".join(status)

    def handle_command(self, command, args, user_id, user_role=None):
        cmd = command.lower().lstrip("/")
        
        if cmd == "weather_info":
            return self._weather_info()
        elif cmd == "weather":
            return self._get_weather(args)
        
        return f"❌ Unknown weather command: {command}"

    def _weather_info(self):
        """Show weather plugin information"""
        return (
            "🌤 *Weather Plugin Info*\n"
            f"Provider: {self.provider}\n"
            f"Status: {'✅ Active' if self.active else '❌ Inactive'}\n"
            f"API Key: {'✅ Configured' if self.api_key else '❌ Not configured'}"
        )

    def _get_weather(self, args):
        """Get weather for a location"""
        if not self.active:
            return "⚠️ Weather plugin is not active."
        
        if not args or len(args) == 0:
            return "💬 Please provide a location. Usage: /weather Cairo"
        
        # Join all args to support multi-word locations
        location = " ".join(args)
        
        logger.info(f"Fetching weather for location: {location}")
        weather_data = self.weather_api.get_weather(location)
        response = self.weather_api.format_weather_response(weather_data)
        
        return response

    def respond_to_message(self, user_id, text, context=None):
        """Weather plugin doesn't handle direct messages, only commands"""
        return None
