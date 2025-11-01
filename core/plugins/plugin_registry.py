from typing import Dict, Optional


class PluginRegistry:
    """Registry that stores discovered plugin metadata and instances.

    Keeps two maps:
      - available: name -> metadata
      - active: name -> instance
    """

    def __init__(self):
        self.available: Dict[str, dict] = {}
        self.active: Dict[str, object] = {}

    def register_available(self, name: str, metadata: dict):
        self.available[name] = metadata

    def is_available(self, name: str) -> bool:
        return name in self.available

    def activate(self, name: str, instance: object):
        self.active[name] = instance

    def deactivate(self, name: str):
        if name in self.active:
            del self.active[name]

    def is_active(self, name: str) -> bool:
        return name in self.active