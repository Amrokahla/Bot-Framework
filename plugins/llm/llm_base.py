"""
Base class for LLM plugins. All provider-specific LLMs should inherit from this.
"""

class LLMBase:
    def __init__(self, bot, config):
        self.bot = bot
        self.config = config or {}
        self.session_context = {}
        self.api_key = self.config.get("api_key")
        self.temperature = self.config.get("temperature", 0.7)
        self.model_name = self.config.get("model_name")
        self.bot_persona = self.config.get("bot_persona")
        self.provider = self.config.get("provider")
        self.active = False

    @staticmethod
    def name():
        return "llm_base"

    @staticmethod
    def description():
        return "Base class for LLM plugins."

    def activate(self):
        self.active = True

    def deactivate(self):
        self.active = False

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

    def set_bot_persona(self, persona: str):
        self.bot_persona = persona

    def get_bot_persona(self):
        return self.bot_persona or "You are a helpful Telegram bot named {botname}. Only answer questions related to your bot's purpose. Never say you are Gemini or Google AI."

    def respond_to_message(self, user_id, text, context=None):
        raise NotImplementedError("Subclasses must implement respond_to_message.")

    def handle_command(self, command, args, user_id, user_role=None):
        raise NotImplementedError("Subclasses must implement handle_command.")
