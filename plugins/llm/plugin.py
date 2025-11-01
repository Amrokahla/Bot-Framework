

"""
LLM Plugin entry point. Exposes commands and help, delegates to LLMManager for provider logic.
"""

from core.plugins.plugin_base import BasePlugin
from .llm_manager import LLMManager

class LLMPlugin(BasePlugin):
    def __init__(self, bot, config=None):
        super().__init__(bot)
        self.config = config or {}
        self.manager = LLMManager(bot, self.config)

    @staticmethod
    def name():
        return "llm"

    @staticmethod
    def description():
        return "LLM plugin supporting multiple providers (Gemini, OpenAI, etc)."

    def commands(self):
        # Expose all commands supported by the underlying provider
        return self.manager.commands()

    def help_text(self):
        # Expose help from the underlying provider
        return self.manager.help_text()

    def activate(self):
        self.manager.activate()

    def deactivate(self):
        self.manager.deactivate()

    def is_active(self):
        return self.manager.is_active()

    def health_status(self):
        return self.manager.health_status()

    def set_bot_persona(self, persona: str):
        self.manager.set_bot_persona(persona)

    def get_bot_persona(self):
        return self.manager.get_bot_persona()

    def respond_to_message(self, user_id, text, context=None):
        return self.manager.respond_to_message(user_id, text, context)

    def handle_command(self, command, args, user_id, user_role=None):
        return self.manager.handle_command(command, args, user_id, user_role)
