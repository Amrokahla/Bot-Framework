"""
OpenAI LLM implementation for ChatGPT and other OpenAI models.
"""

import openai
from .llm_base import LLMBase

class OpenAILLM(LLMBase):
    @staticmethod
    def name():
        return "openai_llm"

    @staticmethod
    def description():
        return "OpenAI-powered LLM for human-like chat, Q&A, and contextual conversations."

    def commands(self):
        return {
            "/llm_info": "Show LLM model, provider, temperature, persona, and system prompt (admin only)"
        }

    def help_text(self):
        return (
            "🧠 *LLM Plugin (OpenAI)*\n"
            "\nCommands:" + "\n" + "\n".join([f"• {cmd} — {desc}" for cmd, desc in self.commands().items()])
        )

    def activate(self):
        if not self.api_key:
            print("⚠️ OpenAI API key not set in client config. Please configure it before activation.")
            return
        openai.api_key = self.api_key
        self.active = True
        print(f"✅ OpenAI LLM activated with model: {self.model_name}")

    def respond_to_message(self, user_id, text, context=None):
        import logging
        logger = logging.getLogger("openai_llm")
        health = self.health_status()
        logger.info(f"OpenAILLM health check before chat: {health}")
        if not self.api_key or not self.active:
            return f"⚠️ OpenAI LLM not ready: {health}"
        if not text:
            logger.info(f"OpenAILLM: Received empty text from user {user_id}")
            return "💬 Please send a message."
        session_context = context or self.session_context.get(user_id, "")
        prompt = self._build_prompt(session_context, text)
        persona = self.get_bot_persona().format(botname=getattr(self.bot, "username", "Bot"))
        prompt = f"{persona}\n{prompt}"
        logger.info(f"OpenAILLM: Sending prompt to OpenAI for user {user_id}: {prompt}")
        try:
            model_name = self.model_name or self.config.get("model_name", "gpt-3.5-turbo")
            response = openai.ChatCompletion.create(
                model=model_name,
                messages=[{"role": "system", "content": persona}, {"role": "user", "content": text}],
                temperature=self.temperature
            )
            reply = response.choices[0].message["content"]
            reply = self._postprocess_response(reply)
            self.session_context[user_id] = reply
            logger.info(f"OpenAILLM: Final reply sent to user {user_id}: {reply}")
            return reply
        except Exception as e:
            logger.error(f"OpenAILLM: Error contacting OpenAI for user {user_id}: {e}")
            return f"⚠️ Error contacting OpenAI: {e}"

    def handle_command(self, command, args, user_id, user_role=None):
        cmd = command.lower().lstrip("/")
        if cmd == "llm_info":
            if user_role not in ("admin", "superadmin"):
                return "❌ /llm_info is restricted to admin and above."
            return self._llm_info()
        return f"❌ Unknown OpenAI LLM command: {command}"

    def _llm_info(self):
        model_name = self.model_name or self.config.get('model_name', 'gpt-3.5-turbo')
        reply = (
            "🤖 OpenAI LLM Info\n"
            f"Model: {model_name}\n"
            f"Provider: {self.provider}\n"
            f"Temperature: {self.temperature}\n"
        )
        if not reply.strip():
            reply = "⚠️ LLM info not available."
        return reply

    def _build_prompt(self, context, user_input):
        if context:
            return f"Previous conversation:\n{context}\nUser: {user_input}\nBot:"
        else:
            return f"User: {user_input}\nBot:"

    def _postprocess_response(self, text):
        if not text:
            return "⚠️ No response from model."
        return text.strip()
