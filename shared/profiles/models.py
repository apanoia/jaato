"""Data models for agent profiles.

This module defines the core data structures for agent profile configuration,
including the AgentProfile dataclass and related configuration models.
"""

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class ProfileValidationError(Exception):
    """Raised when profile validation fails."""

    def __init__(self, profile_name: str, errors: List[str]):
        self.profile_name = profile_name
        self.errors = errors
        super().__init__(
            f"Profile '{profile_name}' validation failed: {'; '.join(errors)}"
        )


@dataclass
class PluginConfig:
    """Configuration for a single plugin within a profile.

    Attributes:
        name: Plugin name (e.g., 'cli', 'mcp', 'references').
        enabled: Whether the plugin is enabled (default: True).
        config: Plugin-specific configuration dict.
        tools_allowed: Optional list of specific tools to allow from this plugin.
        tools_denied: Optional list of specific tools to deny from this plugin.
    """
    name: str
    enabled: bool = True
    config: Dict[str, Any] = field(default_factory=dict)
    tools_allowed: Optional[List[str]] = None
    tools_denied: Optional[List[str]] = None

    @classmethod
    def from_dict(cls, name: str, data: Dict[str, Any]) -> 'PluginConfig':
        """Create PluginConfig from a dictionary.

        Args:
            name: Plugin name.
            data: Configuration dictionary.

        Returns:
            PluginConfig instance.
        """
        return cls(
            name=name,
            enabled=data.get('enabled', True),
            config=data.get('config', {}),
            tools_allowed=data.get('tools_allowed'),
            tools_denied=data.get('tools_denied'),
        )


@dataclass
class ProfileConfig:
    """Top-level configuration structure for an agent profile.

    This represents the contents of profile.json in a profile folder.

    Attributes:
        name: Unique identifier for this profile.
        description: Human-readable description of the profile's purpose.
        version: Profile schema version (for future compatibility).
        model: Optional model override (e.g., 'gemini-2.5-flash').
        plugins: List of plugin names to enable.
        plugin_configs: Per-plugin configuration overrides.
        max_turns: Maximum conversation turns (default: 20).
        auto_approved: Whether this profile can be used without permission.
        tags: Optional tags for categorization and filtering.
        extends: Optional parent profile name to inherit from.
        scope: Optional description of the profile's scope/boundaries.
        goals: Optional list of goals this profile is designed to achieve.
    """
    name: str
    description: str = ""
    version: str = "1.0"
    model: Optional[str] = None
    plugins: List[str] = field(default_factory=list)
    plugin_configs: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    max_turns: int = 20
    auto_approved: bool = False
    tags: List[str] = field(default_factory=list)
    extends: Optional[str] = None
    scope: Optional[str] = None
    goals: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ProfileConfig':
        """Create ProfileConfig from a dictionary.

        Args:
            data: Configuration dictionary.

        Returns:
            ProfileConfig instance.
        """
        return cls(
            name=data.get('name', ''),
            description=data.get('description', ''),
            version=str(data.get('version', '1.0')),
            model=data.get('model'),
            plugins=data.get('plugins', []),
            plugin_configs=data.get('plugin_configs', {}),
            max_turns=data.get('max_turns', 20),
            auto_approved=data.get('auto_approved', False),
            tags=data.get('tags', []),
            extends=data.get('extends'),
            scope=data.get('scope'),
            goals=data.get('goals', []),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        result = {
            'name': self.name,
            'description': self.description,
            'version': self.version,
            'plugins': self.plugins,
            'max_turns': self.max_turns,
            'auto_approved': self.auto_approved,
        }
        if self.model:
            result['model'] = self.model
        if self.plugin_configs:
            result['plugin_configs'] = self.plugin_configs
        if self.tags:
            result['tags'] = self.tags
        if self.extends:
            result['extends'] = self.extends
        if self.scope:
            result['scope'] = self.scope
        if self.goals:
            result['goals'] = self.goals
        return result


@dataclass
class AgentProfile:
    """Complete agent profile with all loaded configuration.

    This is the fully resolved profile after loading from a folder,
    including system prompt, permissions, references, and all configs.

    Attributes:
        config: The main profile configuration.
        system_prompt: The agent's system prompt/instructions.
        permissions_config: Optional permission policy configuration.
        references_config: Optional references plugin configuration.
        plugin_configs: Fully resolved per-plugin configurations.
        profile_path: Path to the profile folder.
        local_references: Paths to local reference documents.
    """
    config: ProfileConfig
    system_prompt: Optional[str] = None
    permissions_config: Optional[Dict[str, Any]] = None
    references_config: Optional[Dict[str, Any]] = None
    plugin_configs: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    profile_path: Optional[Path] = None
    local_references: List[Path] = field(default_factory=list)

    @property
    def name(self) -> str:
        """Profile name."""
        return self.config.name

    @property
    def description(self) -> str:
        """Profile description."""
        return self.config.description

    @property
    def plugins(self) -> List[str]:
        """List of enabled plugins."""
        return self.config.plugins

    @property
    def model(self) -> Optional[str]:
        """Model override."""
        return self.config.model

    @property
    def max_turns(self) -> int:
        """Maximum conversation turns."""
        return self.config.max_turns

    @property
    def auto_approved(self) -> bool:
        """Whether auto-approved for spawning."""
        return self.config.auto_approved

    @property
    def tags(self) -> List[str]:
        """Profile tags."""
        return self.config.tags

    def get_plugin_config(self, plugin_name: str) -> Dict[str, Any]:
        """Get configuration for a specific plugin.

        Args:
            plugin_name: Name of the plugin.

        Returns:
            Plugin configuration dict (empty dict if not configured).
        """
        return self.plugin_configs.get(plugin_name, {})

    def get_full_system_instructions(self) -> str:
        """Build complete system instructions from all sources.

        Combines:
        - Profile scope and goals (if defined)
        - System prompt
        - Local references content (embedded or paths)

        Returns:
            Complete system instruction string.
        """
        parts = []

        # Add scope and goals if defined
        if self.config.scope or self.config.goals:
            parts.append("# Profile Context")
            if self.config.scope:
                parts.append(f"\n## Scope\n{self.config.scope}")
            if self.config.goals:
                goals_text = "\n".join(f"- {goal}" for goal in self.config.goals)
                parts.append(f"\n## Goals\n{goals_text}")
            parts.append("")

        # Add main system prompt
        if self.system_prompt:
            parts.append(self.system_prompt)

        # Note about local references
        if self.local_references:
            ref_note = "\n\n# Local References Available\n"
            ref_note += "The following reference documents are available in this profile:\n"
            for ref_path in self.local_references:
                ref_note += f"- {ref_path.name}\n"
            parts.append(ref_note)

        return "\n\n".join(parts)

    def to_subagent_profile(self) -> 'SubagentProfile':
        """Convert to SubagentProfile for use with subagent plugin.

        Returns:
            SubagentProfile instance compatible with subagent plugin.
        """
        # Import here to avoid circular dependency
        from ..plugins.subagent.config import SubagentProfile

        return SubagentProfile(
            name=self.name,
            description=self.description,
            plugins=self.plugins,
            plugin_configs=self.plugin_configs,
            system_instructions=self.get_full_system_instructions(),
            model=self.model,
            max_turns=self.max_turns,
            auto_approved=self.auto_approved,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        result = {
            'config': self.config.to_dict(),
            'system_prompt': self.system_prompt,
            'plugin_configs': self.plugin_configs,
        }
        if self.permissions_config:
            result['permissions_config'] = self.permissions_config
        if self.references_config:
            result['references_config'] = self.references_config
        if self.profile_path:
            result['profile_path'] = str(self.profile_path)
        if self.local_references:
            result['local_references'] = [str(p) for p in self.local_references]
        return result
