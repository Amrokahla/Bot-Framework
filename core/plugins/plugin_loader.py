import importlib
import importlib.util
import os
from typing import Optional

PLUGINS_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "plugins"))


class PluginLoader:
    """Responsible for discovering and importing plugin modules from external plugins/ directory."""

    def discover(self):
        """Yield plugin directories found under the plugins root."""
        if not os.path.isdir(PLUGINS_ROOT):
            return []
        for name in os.listdir(PLUGINS_ROOT):
            path = os.path.join(PLUGINS_ROOT, name)
            if os.path.isdir(path) and os.path.exists(os.path.join(path, "main.py")):
                yield name, path

    def load_module(self, name: str, path: str):
        """Dynamically import a plugin main.py and return module object or None."""
        spec = importlib.util.spec_from_file_location(f"plugins.{name}", os.path.join(path, "main.py"))
        if spec is None:
            return None
        mod = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(mod)  # type: ignore
            return mod
        except Exception:
            return None