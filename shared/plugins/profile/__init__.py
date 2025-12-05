"""Profile plugin for agent profile management.

This plugin provides tools for discovering, listing, and using
agent profiles defined as folder-based configurations.
"""

from .plugin import ProfilePlugin, create_plugin

__all__ = ["ProfilePlugin", "create_plugin"]
