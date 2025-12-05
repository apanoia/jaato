"""Profile loading and discovery functionality.

This module handles discovering profile folders and loading their
configuration into AgentProfile instances.
"""

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .models import AgentProfile, ProfileConfig, ProfileValidationError

logger = logging.getLogger(__name__)


# Standard file names within a profile folder
PROFILE_JSON = "profile.json"
SYSTEM_PROMPT_MD = "system_prompt.md"
PERMISSIONS_JSON = "permissions.json"
REFERENCES_JSON = "references.json"
REFERENCES_DIR = "references"
PLUGIN_CONFIGS_DIR = "plugin_configs"


class ProfileLoader:
    """Loader for agent profiles from folder-based configuration.

    The ProfileLoader handles:
    - Discovering profile folders in specified directories
    - Loading and validating profile configuration files
    - Resolving profile inheritance (extends)
    - Building complete AgentProfile instances

    Example usage:
        loader = ProfileLoader()
        loader.add_search_path("./profiles")
        loader.discover()

        profile = loader.load("code_assistant")
    """

    def __init__(self):
        """Initialize the profile loader."""
        self._search_paths: List[Path] = []
        self._discovered: Dict[str, Path] = {}  # name -> path
        self._cache: Dict[str, AgentProfile] = {}  # name -> loaded profile

    def add_search_path(self, path: str | Path) -> None:
        """Add a directory to search for profiles.

        Args:
            path: Directory path to search for profile folders.
        """
        path = Path(path)
        if path.is_dir() and path not in self._search_paths:
            self._search_paths.append(path)
            logger.debug("Added profile search path: %s", path)

    def add_search_paths_from_env(
        self,
        env_var: str = "JAATO_PROFILE_PATHS"
    ) -> None:
        """Add search paths from an environment variable.

        The environment variable should contain colon-separated paths.

        Args:
            env_var: Name of the environment variable.
        """
        paths_str = os.environ.get(env_var, "")
        if paths_str:
            for path_str in paths_str.split(":"):
                path = Path(path_str.strip()).expanduser()
                if path.is_dir():
                    self.add_search_path(path)

    def discover(self) -> Dict[str, Path]:
        """Discover all profile folders in search paths.

        A valid profile folder must contain a profile.json file.

        Returns:
            Dict mapping profile names to their folder paths.
        """
        self._discovered.clear()

        for search_path in self._search_paths:
            if not search_path.is_dir():
                continue

            for item in search_path.iterdir():
                if item.is_dir():
                    profile_json = item / PROFILE_JSON
                    if profile_json.exists():
                        # Try to extract name from profile.json
                        try:
                            with open(profile_json, 'r', encoding='utf-8') as f:
                                data = json.load(f)
                            name = data.get('name', item.name)
                        except (json.JSONDecodeError, IOError):
                            name = item.name

                        if name in self._discovered:
                            logger.warning(
                                "Profile '%s' at %s shadows existing profile at %s",
                                name, item, self._discovered[name]
                            )
                        self._discovered[name] = item
                        logger.debug("Discovered profile '%s' at %s", name, item)

        return self._discovered.copy()

    def list_profiles(self) -> List[Dict[str, Any]]:
        """List all discovered profiles with basic info.

        Returns:
            List of dicts with profile name, path, and description.
        """
        profiles = []
        for name, path in sorted(self._discovered.items()):
            info = {'name': name, 'path': str(path)}
            try:
                config = self._load_profile_config(path)
                info['description'] = config.description
                info['tags'] = config.tags
                info['plugins'] = config.plugins
            except Exception as e:
                info['error'] = str(e)
            profiles.append(info)
        return profiles

    def load(self, name: str, use_cache: bool = True) -> AgentProfile:
        """Load a profile by name.

        Args:
            name: Profile name to load.
            use_cache: Whether to use cached profile if available.

        Returns:
            Fully loaded AgentProfile instance.

        Raises:
            FileNotFoundError: If profile not found.
            ProfileValidationError: If profile validation fails.
        """
        if use_cache and name in self._cache:
            return self._cache[name]

        if name not in self._discovered:
            raise FileNotFoundError(
                f"Profile '{name}' not found. Available: {list(self._discovered.keys())}"
            )

        path = self._discovered[name]
        profile = self._load_from_path(path)

        # Handle inheritance
        if profile.config.extends:
            profile = self._resolve_inheritance(profile)

        self._cache[name] = profile
        return profile

    def load_from_path(self, path: str | Path) -> AgentProfile:
        """Load a profile directly from a folder path.

        Args:
            path: Path to the profile folder.

        Returns:
            Fully loaded AgentProfile instance.

        Raises:
            FileNotFoundError: If path doesn't exist or isn't a valid profile.
            ProfileValidationError: If profile validation fails.
        """
        path = Path(path)
        if not path.is_dir():
            raise FileNotFoundError(f"Profile path is not a directory: {path}")

        profile_json = path / PROFILE_JSON
        if not profile_json.exists():
            raise FileNotFoundError(
                f"Not a valid profile folder (missing profile.json): {path}"
            )

        profile = self._load_from_path(path)

        # Handle inheritance
        if profile.config.extends:
            profile = self._resolve_inheritance(profile)

        return profile

    def clear_cache(self) -> None:
        """Clear the profile cache."""
        self._cache.clear()

    def _load_from_path(self, path: Path) -> AgentProfile:
        """Load a profile from a folder path.

        Args:
            path: Path to the profile folder.

        Returns:
            AgentProfile instance (before inheritance resolution).
        """
        # Load main config
        config = self._load_profile_config(path)

        # Validate config
        errors = self._validate_config(config)
        if errors:
            raise ProfileValidationError(config.name, errors)

        # Load optional system prompt
        system_prompt = self._load_system_prompt(path)

        # Load optional permissions config
        permissions_config = self._load_json_file(path / PERMISSIONS_JSON)

        # Load optional references config
        references_config = self._load_json_file(path / REFERENCES_JSON)

        # Discover local reference documents
        local_references = self._discover_local_references(path)

        # Load plugin-specific configs
        plugin_configs = self._load_plugin_configs(path, config)

        return AgentProfile(
            config=config,
            system_prompt=system_prompt,
            permissions_config=permissions_config,
            references_config=references_config,
            plugin_configs=plugin_configs,
            profile_path=path,
            local_references=local_references,
        )

    def _load_profile_config(self, path: Path) -> ProfileConfig:
        """Load the main profile.json configuration.

        Args:
            path: Profile folder path.

        Returns:
            ProfileConfig instance.
        """
        profile_json = path / PROFILE_JSON
        with open(profile_json, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Use folder name as default if name not specified
        if 'name' not in data:
            data['name'] = path.name

        return ProfileConfig.from_dict(data)

    def _load_system_prompt(self, path: Path) -> Optional[str]:
        """Load system prompt from system_prompt.md.

        Args:
            path: Profile folder path.

        Returns:
            System prompt content or None if not found.
        """
        prompt_path = path / SYSTEM_PROMPT_MD
        if prompt_path.exists():
            with open(prompt_path, 'r', encoding='utf-8') as f:
                return f.read().strip()
        return None

    def _load_json_file(self, path: Path) -> Optional[Dict[str, Any]]:
        """Load a JSON file if it exists.

        Args:
            path: Path to JSON file.

        Returns:
            Parsed JSON dict or None if file doesn't exist.
        """
        if path.exists():
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except json.JSONDecodeError as e:
                logger.warning("Invalid JSON in %s: %s", path, e)
        return None

    def _discover_local_references(self, path: Path) -> List[Path]:
        """Discover local reference documents in the references/ folder.

        Args:
            path: Profile folder path.

        Returns:
            List of paths to reference documents.
        """
        references_dir = path / REFERENCES_DIR
        references = []

        if references_dir.is_dir():
            for item in references_dir.iterdir():
                if item.is_file() and item.suffix in ('.md', '.txt', '.json', '.yaml', '.yml'):
                    references.append(item)

        return sorted(references)

    def _load_plugin_configs(
        self,
        path: Path,
        config: ProfileConfig
    ) -> Dict[str, Dict[str, Any]]:
        """Load plugin-specific configurations.

        Merges configs from:
        1. plugin_configs/ directory (individual JSON files)
        2. plugin_configs in profile.json

        Args:
            path: Profile folder path.
            config: Main profile configuration.

        Returns:
            Dict mapping plugin names to their configurations.
        """
        plugin_configs: Dict[str, Dict[str, Any]] = {}

        # Load from plugin_configs/ directory
        configs_dir = path / PLUGIN_CONFIGS_DIR
        if configs_dir.is_dir():
            for item in configs_dir.iterdir():
                if item.is_file() and item.suffix == '.json':
                    plugin_name = item.stem
                    loaded = self._load_json_file(item)
                    if loaded:
                        plugin_configs[plugin_name] = loaded

        # Merge/override with inline configs from profile.json
        for plugin_name, inline_config in config.plugin_configs.items():
            if plugin_name in plugin_configs:
                # Merge: inline config overrides file config
                plugin_configs[plugin_name].update(inline_config)
            else:
                plugin_configs[plugin_name] = inline_config

        return plugin_configs

    def _validate_config(self, config: ProfileConfig) -> List[str]:
        """Validate a profile configuration.

        Args:
            config: ProfileConfig to validate.

        Returns:
            List of validation error messages (empty if valid).
        """
        errors: List[str] = []

        if not config.name:
            errors.append("Profile name is required")

        if config.max_turns < 1:
            errors.append("max_turns must be at least 1")

        if config.version not in ("1.0", "1"):
            errors.append(f"Unsupported profile version: {config.version}")

        return errors

    def _resolve_inheritance(self, profile: AgentProfile) -> AgentProfile:
        """Resolve profile inheritance (extends).

        Args:
            profile: Profile with extends field set.

        Returns:
            Profile with inherited values merged.
        """
        parent_name = profile.config.extends
        if not parent_name:
            return profile

        if parent_name not in self._discovered:
            raise ProfileValidationError(
                profile.name,
                [f"Parent profile '{parent_name}' not found"]
            )

        # Load parent (recursively handles its inheritance)
        parent = self.load(parent_name)

        # Create merged config
        merged_config = ProfileConfig(
            name=profile.config.name,
            description=profile.config.description or parent.config.description,
            version=profile.config.version,
            model=profile.config.model or parent.config.model,
            # Child plugins extend parent plugins
            plugins=list(dict.fromkeys(parent.config.plugins + profile.config.plugins)),
            plugin_configs={**parent.config.plugin_configs, **profile.config.plugin_configs},
            max_turns=profile.config.max_turns if profile.config.max_turns != 20 else parent.config.max_turns,
            auto_approved=profile.config.auto_approved,
            tags=list(dict.fromkeys(parent.config.tags + profile.config.tags)),
            extends=None,  # Clear after resolution
            scope=profile.config.scope or parent.config.scope,
            goals=profile.config.goals or parent.config.goals,
        )

        # Merge system prompts (child appends to parent)
        merged_system_prompt = None
        if parent.system_prompt and profile.system_prompt:
            merged_system_prompt = f"{parent.system_prompt}\n\n{profile.system_prompt}"
        else:
            merged_system_prompt = profile.system_prompt or parent.system_prompt

        # Merge plugin configs (child overrides parent)
        merged_plugin_configs = {**parent.plugin_configs, **profile.plugin_configs}

        # Merge references (child extends parent)
        merged_local_references = list(dict.fromkeys(
            parent.local_references + profile.local_references
        ))

        # Permissions: child completely overrides parent (no merge for security)
        permissions_config = profile.permissions_config or parent.permissions_config

        # References config: child overrides parent
        references_config = profile.references_config or parent.references_config

        return AgentProfile(
            config=merged_config,
            system_prompt=merged_system_prompt,
            permissions_config=permissions_config,
            references_config=references_config,
            plugin_configs=merged_plugin_configs,
            profile_path=profile.profile_path,
            local_references=merged_local_references,
        )


# Module-level convenience functions

_default_loader: Optional[ProfileLoader] = None


def get_default_loader() -> ProfileLoader:
    """Get or create the default profile loader.

    The default loader searches:
    - ./profiles
    - ~/.config/jaato/profiles
    - Paths from JAATO_PROFILE_PATHS env var

    Returns:
        ProfileLoader instance.
    """
    global _default_loader

    if _default_loader is None:
        _default_loader = ProfileLoader()

        # Add default search paths
        cwd_profiles = Path.cwd() / "profiles"
        if cwd_profiles.is_dir():
            _default_loader.add_search_path(cwd_profiles)

        config_profiles = Path.home() / ".config" / "jaato" / "profiles"
        if config_profiles.is_dir():
            _default_loader.add_search_path(config_profiles)

        # Add paths from environment
        _default_loader.add_search_paths_from_env()

        # Discover profiles
        _default_loader.discover()

    return _default_loader


def load_profile(name: str) -> AgentProfile:
    """Load a profile by name using the default loader.

    Args:
        name: Profile name to load.

    Returns:
        AgentProfile instance.
    """
    return get_default_loader().load(name)


def discover_profiles() -> Dict[str, Path]:
    """Discover available profiles using the default loader.

    Returns:
        Dict mapping profile names to their folder paths.
    """
    return get_default_loader().discover()
