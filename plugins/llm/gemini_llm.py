"""
Gemini LLM implementation for Google Generative AI.
"""

import google.generativeai as genai
import re
from .llm_base import LLMBase

class GeminiLLM(LLMBase):
    @staticmethod
    def name():
        return "gemini_llm"

    @staticmethod
    def description():
        return "Gemini-powered LLM for human-like chat, Q&A, and contextual conversations."

    def commands(self):
        return {
            "/llm_info": "Show LLM model, provider, temperature, persona, and system prompt (admin only)"
        }

    def help_text(self):
        return (
            "🧠 *LLM Plugin (Gemini)*\n"
            "\nCommands:" + "\n" + "\n".join([f"• {cmd} — {desc}" for cmd, desc in self.commands().items()])
        )

    def activate(self):
        if not self.api_key:
            print("⚠️ Gemini API key not set in client config. Please configure it before activation.")
            return
        if not self.model_name:
            self.model_name = self.config.get("model_name", "gemini-2.5-flash")
        genai.configure(api_key=self.api_key)
        self.active = True
        print(f"✅ Gemini LLM activated with model: {self.model_name}")

    def respond_to_message(self, user_id, text, context=None):
        import logging
        logger = logging.getLogger("gemini_llm")
        health = self.health_status()
        logger.info(f"GeminiLLM health check before chat: {health}")
        if not self.api_key or not self.active:
            return f"⚠️ Gemini LLM not ready: {health}"
        if not text:
            logger.info(f"GeminiLLM: Received empty text from user {user_id}")
            return "💬 Please send a message."
        session_context = context or self.session_context.get(user_id, "")
        prompt = self._build_prompt(session_context, text)
        persona = self.get_bot_persona().format(botname=getattr(self.bot, "username", "Bot"))
        prompt = f"{persona}\n{prompt}"
        logger.info(f"GeminiLLM: Sending prompt to Gemini for user {user_id}: {prompt}")
        try:
            model_name = self.model_name or self.config.get("model_name", "gemini-2.5-flash")
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
            logger.info(f"GeminiLLM: Gemini raw response for user {user_id}: {getattr(response, 'text', None)}")
            reply = self._postprocess_response(getattr(response, 'text', None))
            self.session_context[user_id] = reply
            logger.info(f"GeminiLLM: Final reply sent to user {user_id}: {reply}")
            return reply
        except Exception as e:
            logger.error(f"GeminiLLM: Error contacting Gemini for user {user_id}: {e}")
            return f"⚠️ Error contacting Gemini: {e}"

    def handle_command(self, command, args, user_id, user_role=None):
        cmd = command.lower().lstrip("/")
        if cmd == "llm_info":
            if user_role not in ("admin", "superadmin"):
                return "❌ /llm_info is restricted to admin and above."
            return self._llm_info()
        return f"❌ Unknown Gemini LLM command: {command}"

    def _llm_info(self):
        model_name = self.model_name or self.config.get('model_name', 'gemini-2.5-flash')
        reply = (
            "🤖 Gemini LLM Info\n"
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
        text = re.sub(r"\n{2,}", "\n", text)
        text = text.strip()
        return text
