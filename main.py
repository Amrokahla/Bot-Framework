import logging
from core.bot.telegram_bot import TelegramBot
from core.config.config import get_settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    settings = get_settings()
    import json
    import os
    config_path = os.path.join(os.path.dirname(__file__), "client_config.json")
    active_plugins = []
    client_cfg = {}
    if os.path.exists(config_path):
        with open(config_path) as f:
            client_cfg = json.load(f)
        active_plugins = client_cfg.get("active_plugins", [])

    # Set active_plugins before bot construction
    bot = TelegramBot(settings=settings)
    bot.active_plugins = active_plugins

    # Activate plugins only after config is set
    if hasattr(bot, "plugin_manager"):
        # First, instantiate plugins but do NOT activate yet
        for pname in active_plugins:
            if pname in bot.plugin_manager.available_plugins:
                bot.plugin_manager.activate_plugin(pname)
        # Update bot.plugins dict
        bot.plugins = dict(bot.plugin_manager.plugins)
        # Set config attributes on plugin instances BEFORE activation
        for pname in active_plugins:
            if pname in bot.plugins:
                plugin = bot.plugins[pname]
                plugin_cfg = client_cfg.get(pname, {})
                if pname == "llm":
                    if "bot_persona" in plugin_cfg:
                        plugin.set_bot_persona(plugin_cfg["bot_persona"])
                    if "api_key" in plugin_cfg:
                        plugin.manager.llm.api_key = plugin_cfg["api_key"]
                    if "temperature" in plugin_cfg:
                        plugin.manager.llm.temperature = plugin_cfg["temperature"]
                    if "pre_prompt" in plugin_cfg:
                        plugin.manager.llm.pre_prompt = plugin_cfg["pre_prompt"]
                    if "provider" in plugin_cfg:
                        plugin.manager.llm.provider = plugin_cfg["provider"]
                    if "model_name" in plugin_cfg:
                        plugin.manager.llm.model_name = plugin_cfg["model_name"]
                # For other plugins, pass config as needed
                # Example: plugin.load_config(plugin_cfg)
        # Now, activate plugins after config is set
        for pname in active_plugins:
            if pname in bot.plugins:
                bot.plugins[pname].activate()
    # Register plugin commands after activation and config
    if hasattr(bot, "message_handler"):
        bot.message_handler.register_all_plugin_commands()

    try:
        bot.start_polling()
    except KeyboardInterrupt:
        logger.info("🛑 Stopping bot gracefully...")
        # Stop all background tasks
        try:
            if hasattr(bot, "admin_tools") and bot.admin_tools:
                bot.admin_tools.stop()
        except Exception as e:
            logger.error(f"Error stopping admin tools: {e}")
        bot.stop()
        logger.info("Bot stopped.")

if __name__ == "__main__":
    main()
