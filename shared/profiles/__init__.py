"""Agent profile management module.

This module provides folder-based agent profile configuration, allowing
all aspects of an agent's behavior to be defined in a single location:

- System prompt (initial instructions)
- Plugins to enable
- Plugin configurations
- Permission policies
- Reference documents
- Scope and goals

Profile Folder Structure:
    profiles/
    ├── my_profile/
    │   ├── profile.json          # Main profile configuration
    │   ├── system_prompt.md      # Agent's system prompt
    │   ├── permissions.json      # Optional permission policy
    │   ├── references.json       # Optional reference sources config
    │   ├── references/           # Local reference documents
    │   │   ├── api_docs.md
    │   │   └── guidelines.md
    │   └── plugin_configs/       # Per-plugin configurations
    │       ├── cli.json
    │       └── mcp.json
"""

from .models import (
    AgentProfile,
    ProfileConfig,
    ProfileValidationError,
)
from .loader import (
    ProfileLoader,
    load_profile,
    discover_profiles,
)

__all__ = [
    "AgentProfile",
    "ProfileConfig",
    "ProfileValidationError",
    "ProfileLoader",
    "load_profile",
    "discover_profiles",
]
