"""Profile plugin for agent profile management.

This plugin provides tools for discovering, listing, and using
agent profiles defined as folder-based configurations.
"""

import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from google.genai import types

from ..base import UserCommand
from ...profiles import (
    AgentProfile,
    ProfileLoader,
    ProfileValidationError,
)

logger = logging.getLogger(__name__)


class ProfilePlugin:
    """Plugin for managing agent profiles.

    This plugin provides:
    - Profile discovery and listing
    - Profile information retrieval
    - Integration with subagent plugin for spawning profiled agents

    Configuration options:
        search_paths: List of directories to search for profiles
        auto_discover: Whether to auto-discover on initialize (default: True)
    """

    PLUGIN_KIND = "tool"  # For registry discovery

    def __init__(self):
        """Initialize the profile plugin."""
        self._loader: Optional[ProfileLoader] = None
        self._initialized: bool = False
        self._config: Dict[str, Any] = {}

    @property
    def name(self) -> str:
        """Unique identifier for this plugin."""
        return "profile"

    def initialize(self, config: Optional[Dict[str, Any]] = None) -> None:
        """Initialize the plugin with configuration.

        Args:
            config: Configuration dict containing:
                - search_paths: List of directories to search for profiles
                - auto_discover: Whether to auto-discover profiles (default: True)
        """
        self._config = config or {}
        self._loader = ProfileLoader()

        # Add configured search paths
        search_paths = self._config.get('search_paths', [])
        for path in search_paths:
            self._loader.add_search_path(Path(path).expanduser())

        # Add default paths if none configured
        if not search_paths:
            # Current working directory profiles/
            cwd_profiles = Path.cwd() / "profiles"
            if cwd_profiles.is_dir():
                self._loader.add_search_path(cwd_profiles)

            # User config directory
            config_profiles = Path.home() / ".config" / "jaato" / "profiles"
            if config_profiles.is_dir():
                self._loader.add_search_path(config_profiles)

        # Add paths from environment
        self._loader.add_search_paths_from_env()

        # Auto-discover profiles
        if self._config.get('auto_discover', True):
            discovered = self._loader.discover()
            logger.info("Discovered %d profiles", len(discovered))

        self._initialized = True

    def shutdown(self) -> None:
        """Clean up plugin resources."""
        if self._loader:
            self._loader.clear_cache()
        self._loader = None
        self._initialized = False

    def get_function_declarations(self) -> List[types.FunctionDeclaration]:
        """Return function declarations for profile tools."""
        return [
            types.FunctionDeclaration(
                name='listProfiles',
                description=(
                    'List all available agent profiles. Profiles define complete '
                    'agent configurations including tools, permissions, and prompts.'
                ),
                parameters_json_schema={
                    "type": "object",
                    "properties": {
                        "tags": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Filter profiles by tags"
                        }
                    },
                    "required": []
                }
            ),
            types.FunctionDeclaration(
                name='getProfileInfo',
                description=(
                    'Get detailed information about a specific agent profile, '
                    'including its plugins, system prompt, and configuration.'
                ),
                parameters_json_schema={
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Name of the profile to get info for"
                        }
                    },
                    "required": ["name"]
                }
            ),
        ]

    def get_executors(self) -> Dict[str, Callable[[Dict[str, Any]], Any]]:
        """Return mapping of tool names to executor functions."""
        return {
            'listProfiles': self._execute_list_profiles,
            'getProfileInfo': self._execute_get_profile_info,
            # User command aliases
            'profiles': self._execute_list_profiles,
        }

    def get_system_instructions(self) -> Optional[str]:
        """Return system instructions describing profile capabilities."""
        if not self._loader:
            return None

        profiles = self._loader.list_profiles()
        if not profiles:
            return None

        parts = [
            "# Agent Profiles",
            "",
            "The following agent profiles are available for reference or spawning:",
            ""
        ]

        for profile in profiles:
            tags_str = f" [{', '.join(profile.get('tags', []))}]" if profile.get('tags') else ""
            parts.append(f"- **{profile['name']}**{tags_str}: {profile.get('description', 'No description')}")

        parts.extend([
            "",
            "Use `listProfiles` to see all available profiles.",
            "Use `getProfileInfo` to see detailed configuration for a profile.",
        ])

        return "\n".join(parts)

    def get_auto_approved_tools(self) -> List[str]:
        """Return tools that should be auto-approved."""
        return ['listProfiles', 'getProfileInfo']

    def get_user_commands(self) -> List[UserCommand]:
        """Return user-facing commands for direct invocation."""
        return [
            UserCommand(
                "profiles",
                "List available agent profiles",
                share_with_model=True
            ),
        ]

    def _execute_list_profiles(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """List available profiles.

        Args:
            args: Tool arguments containing optional 'tags' filter.

        Returns:
            Dict with list of profiles.
        """
        if not self._loader:
            return {
                'profiles': [],
                'error': 'Profile plugin not initialized'
            }

        profiles = self._loader.list_profiles()
        filter_tags = args.get('tags', [])

        if filter_tags:
            profiles = [
                p for p in profiles
                if any(tag in p.get('tags', []) for tag in filter_tags)
            ]

        return {
            'profiles': profiles,
            'total': len(profiles),
        }

    def _execute_get_profile_info(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get detailed info about a profile.

        Args:
            args: Tool arguments containing 'name'.

        Returns:
            Dict with profile details.
        """
        if not self._loader:
            return {'error': 'Profile plugin not initialized'}

        name = args.get('name')
        if not name:
            return {'error': 'Profile name is required'}

        try:
            profile = self._loader.load(name)
            return {
                'name': profile.name,
                'description': profile.description,
                'plugins': profile.plugins,
                'model': profile.model,
                'max_turns': profile.max_turns,
                'auto_approved': profile.auto_approved,
                'tags': profile.tags,
                'scope': profile.config.scope,
                'goals': profile.config.goals,
                'has_system_prompt': profile.system_prompt is not None,
                'has_permissions': profile.permissions_config is not None,
                'has_references': profile.references_config is not None,
                'local_references': [str(p.name) for p in profile.local_references],
                'plugin_configs': list(profile.plugin_configs.keys()),
                'path': str(profile.profile_path) if profile.profile_path else None,
            }
        except FileNotFoundError as e:
            return {'error': str(e)}
        except ProfileValidationError as e:
            return {'error': str(e)}

    # Public API for programmatic access

    def get_loader(self) -> Optional[ProfileLoader]:
        """Get the profile loader instance."""
        return self._loader

    def load_profile(self, name: str) -> AgentProfile:
        """Load a profile by name.

        Args:
            name: Profile name.

        Returns:
            AgentProfile instance.

        Raises:
            FileNotFoundError: If profile not found.
            ProfileValidationError: If profile invalid.
        """
        if not self._loader:
            raise RuntimeError("Profile plugin not initialized")
        return self._loader.load(name)

    def add_search_path(self, path: str | Path) -> None:
        """Add a search path for profiles.

        Args:
            path: Directory path to search.
        """
        if self._loader:
            self._loader.add_search_path(path)
            self._loader.discover()


def create_plugin() -> ProfilePlugin:
    """Factory function to create the profile plugin.

    Returns:
        ProfilePlugin instance.
    """
    return ProfilePlugin()
