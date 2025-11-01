"""
LLMManager routes requests to the correct LLM implementation based on provider in config.
"""

from .gemini_llm import GeminiLLM
from .openai_llm import OpenAILLM

class LLMManager:
    def __init__(self, bot, config):
        self.bot = bot
        self.config = config or {}
        self.provider = self.config.get("provider", "google")
        self.llm = self._init_llm()

    def _init_llm(self):
        if self.provider == "google":
            return GeminiLLM(self.bot, self.config)
        elif self.provider == "openai":
            return OpenAILLM(self.bot, self.config)
        else:
            raise ValueError(f"Unsupported LLM provider: {self.provider}")

    def commands(self):
        return self.llm.commands() if hasattr(self.llm, "commands") else {}

    def help_text(self):
        return self.llm.help_text() if hasattr(self.llm, "help_text") else ""

    def activate(self):
        self.llm.activate()

    def deactivate(self):
        self.llm.deactivate()

    def is_active(self):
        return self.llm.is_active()

    def health_status(self):
        return self.llm.health_status()

    def set_bot_persona(self, persona: str):
        self.llm.set_bot_persona(persona)

    def get_bot_persona(self):
        return self.llm.get_bot_persona()

    def respond_to_message(self, user_id, text, context=None):
        return self.llm.respond_to_message(user_id, text, context)

    def handle_command(self, command, args, user_id, user_role=None):
        return self.llm.handle_command(command, args, user_id, user_role)
