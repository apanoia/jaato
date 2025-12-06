# Agent Profiles

Agent profiles provide a way to define complete agent configurations in a folder-based structure. This allows you to organize all aspects of an agent's behavior in a single location.

## Overview

An agent profile is a folder containing configuration files that define:
- **System prompt**: The agent's initial instructions and persona
- **Plugins**: Which plugins to enable and how to configure them
- **Permissions**: What the agent is allowed to do
- **References**: Documentation and context the agent should have access to
- **Scope and Goals**: Clear boundaries and objectives

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Profile Folder                                  │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐              │
│  │  profile.json   │  │system_prompt.md │  │permissions.json │              │
│  │  (required)     │  │  (optional)     │  │  (optional)     │              │
│  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘              │
│           │                    │                    │                        │
│  ┌────────┴────────┐  ┌────────┴────────┐  ┌───────┴────────┐               │
│  │references.json  │  │  references/    │  │ plugin_configs/│               │
│  │  (optional)     │  │  *.md, *.txt    │  │  cli.json, ... │               │
│  └─────────────────┘  └─────────────────┘  └────────────────┘               │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                             ProfileLoader                                    │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                   │
│  │   discover() │───▶│    load()    │───▶│ AgentProfile │                   │
│  └──────────────┘    └──────────────┘    └──────┬───────┘                   │
│         │                                        │                           │
│         ▼                                        │ resolve inheritance       │
│  Search paths:                                   │ (extends)                 │
│  - ./profiles                                    │                           │
│  - ~/.config/jaato/profiles                      ▼                           │
│  - JAATO_PROFILE_PATHS                  ┌───────────────┐                   │
│                                         │ Merged Config │                   │
│                                         └───────┬───────┘                   │
└─────────────────────────────────────────────────┼───────────────────────────┘
                                                  │
                                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                             JaatoClient                                      │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                     configure_from_profile()                            │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐   │ │
│  │  │   Create    │  │  Configure  │  │    Setup    │  │   Apply     │   │ │
│  │  │  Registry   │─▶│   Plugins   │─▶│ Permissions │─▶│   System    │   │ │
│  │  │             │  │             │  │             │  │   Prompt    │   │ │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘   │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                    │                                         │
│                                    ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │                        Configured Agent                                  ││
│  │  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐            ││
│  │  │  Plugins  │  │Permission │  │References │  │  System   │            ││
│  │  │  (cli,    │  │  Policy   │  │  Sources  │  │Instructions│           ││
│  │  │  mcp,...) │  │           │  │           │  │           │            ││
│  │  └───────────┘  └───────────┘  └───────────┘  └───────────┘            ││
│  └─────────────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────────────┘
```

### Component Relationships

```
AgentProfile
├── config: ProfileConfig          # From profile.json
│   ├── name, description
│   ├── plugins[]                  # Plugin names to enable
│   ├── plugin_configs{}           # Inline plugin configs
│   ├── extends                    # Parent profile (inheritance)
│   └── scope, goals[]             # Agent boundaries
│
├── system_prompt                  # From system_prompt.md
├── permissions_config             # From permissions.json
├── references_config              # From references.json
├── plugin_configs{}               # Merged from plugin_configs/*.json
└── local_references[]             # Files in references/
```

## Folder Structure

```
profiles/
├── my_profile/
│   ├── profile.json          # Main profile configuration (required)
│   ├── system_prompt.md      # Agent's system instructions
│   ├── permissions.json      # Permission policy configuration
│   ├── references.json       # Reference sources configuration
│   ├── references/           # Local reference documents
│   │   ├── api_docs.md
│   │   └── guidelines.md
│   └── plugin_configs/       # Per-plugin configurations
│       ├── cli.json
│       └── mcp.json
```

## Profile Configuration (profile.json)

The main configuration file defines the profile's metadata and structure:

```json
{
  "name": "code_assistant",
  "description": "A specialized assistant for software development",
  "version": "1.0",
  "model": "gemini-2.5-flash",
  "plugins": ["cli", "todo", "references"],
  "plugin_configs": {
    "cli": {
      "working_directory": "."
    }
  },
  "max_turns": 30,
  "auto_approved": false,
  "tags": ["development", "code"],
  "extends": "base",
  "scope": "Software development tasks",
  "goals": [
    "Write clean code",
    "Follow best practices"
  ]
}
```

### Configuration Options

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Unique identifier for the profile |
| `description` | string | Human-readable description |
| `version` | string | Profile schema version (currently "1.0") |
| `model` | string | Optional model override |
| `plugins` | string[] | List of plugins to enable |
| `plugin_configs` | object | Per-plugin configuration overrides |
| `max_turns` | number | Maximum conversation turns (default: 20) |
| `auto_approved` | boolean | Whether the profile can be used without permission |
| `tags` | string[] | Tags for categorization and filtering |
| `extends` | string | Parent profile to inherit from |
| `scope` | string | Description of the profile's boundaries |
| `goals` | string[] | List of goals the profile is designed to achieve |

## Profile Inheritance

Profiles can extend other profiles using the `extends` field:

```json
{
  "name": "python_developer",
  "extends": "code_assistant",
  "plugins": ["pytest"],
  "tags": ["python"]
}
```

When extending:
- **Plugins**: Child plugins are added to parent plugins
- **Plugin configs**: Child configs override parent configs
- **Tags**: Child tags are added to parent tags
- **System prompt**: Child prompt is appended to parent prompt
- **Permissions**: Child permissions completely replace parent permissions
- **Scope/Goals**: Child values override parent if specified

## System Prompt (system_prompt.md)

The system prompt file contains the agent's core instructions in Markdown format:

```markdown
# Code Assistant

You are a specialized code assistant focused on software development.

## Capabilities

- Code generation and review
- Debugging assistance
- Documentation generation

## Guidelines

- Write clean, maintainable code
- Follow established coding standards
- Ask clarifying questions when needed
```

## Permissions (permissions.json)

Define what the agent is allowed to do:

```json
{
  "version": "1.0",
  "defaultPolicy": "ask",
  "blacklist": {
    "tools": [],
    "patterns": ["rm -rf /*", "sudo *"],
    "arguments": {
      "cli_based_tool": {
        "command": ["sudo", "shutdown"]
      }
    }
  },
  "whitelist": {
    "tools": ["addTodo", "listTodos"],
    "patterns": ["git *", "npm *", "python *"]
  },
  "actor": {
    "type": "console",
    "timeout": 30
  }
}
```

## References

### Configuration (references.json)

```json
{
  "sources": [
    {
      "id": "coding_standards",
      "name": "Coding Standards",
      "description": "Project coding standards",
      "type": "local",
      "mode": "auto",
      "path": "references/coding_standards.md",
      "tags": ["standards"]
    }
  ]
}
```

### Local References (references/)

Place reference documents in the `references/` folder. Supported formats:
- Markdown (`.md`)
- Text (`.txt`)
- JSON (`.json`)
- YAML (`.yaml`, `.yml`)

## Plugin Configurations (plugin_configs/)

Store per-plugin configurations as separate JSON files. These are merged with inline `plugin_configs` from profile.json.

### Available Plugin Options

**cli** - Command execution:
```json
{
  "timeout": 30,
  "max_output_chars": 50000,
  "extra_paths": ["/usr/local/bin"]
}
```

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `timeout` | int | 120 | Max seconds to wait for command |
| `max_output_chars` | int | 50000 | Max characters to return |
| `extra_paths` | string[] | [] | Additional PATH entries |

**mcp** - MCP server connections:
```json
{
  "config_path": ".mcp.json"
}
```

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `config_path` | string | null | Path to custom .mcp.json file |

**todo** - Plan tracking:
```json
{
  "reporter_type": "console",
  "storage_type": "memory"
}
```

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `config_path` | string | null | Path to todo.json file |
| `reporter_type` | string | "console" | Reporter type: "console", "webhook", "file" |
| `storage_type` | string | "memory" | Storage type: "memory", "file", "hybrid" |
| `storage_path` | string | null | Path for file-based storage |

**references** - Documentation sources:
```json
{
  "actor_type": "console",
  "actor_config": {"timeout": 30},
  "sources": []
}
```

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `config_path` | string | null | Path to references.json file |
| `actor_type` | string | "console" | Actor type: "console", "webhook", "file" |
| `actor_config` | object | {} | Actor-specific config (timeout, endpoint, etc.) |
| `sources` | array | [] | Inline reference sources (overrides file) |

Note: Command filtering (allowed/denied commands) should be configured via `permissions.json`, not plugin configs.

## Using Profiles

### With JaatoClient

```python
from shared.jaato_client import JaatoClient

client = JaatoClient()
client.connect(project_id, location, model_name)

# Load by name (searches ./profiles and ~/.config/jaato/profiles)
profile = client.configure_from_profile("code_assistant")

# Load by path
profile = client.configure_from_profile("./profiles/my_profile")

# Use the configured client
response = client.send_message("Help me write a function")
```

### With ProfileLoader

```python
from shared.profiles import ProfileLoader

loader = ProfileLoader()
loader.add_search_path("./profiles")
loader.add_search_paths_from_env()  # JAATO_PROFILE_PATHS
loader.discover()

# List available profiles
profiles = loader.list_profiles()

# Load a specific profile
profile = loader.load("code_assistant")
print(profile.name)
print(profile.plugins)
print(profile.get_full_system_instructions())
```

### Environment Variable

Set `JAATO_PROFILE_PATHS` to add additional search paths (colon-separated):

```bash
export JAATO_PROFILE_PATHS="/path/to/profiles:/another/path"
```

## Profile Plugin

The profile plugin provides tools for listing and inspecting profiles:

```python
registry.expose_tool("profile", {"search_paths": ["./profiles"]})
```

Available tools:
- `listProfiles`: List all available profiles
- `getProfileInfo`: Get detailed information about a profile

## Best Practices

1. **Keep profiles focused**: Each profile should have a clear purpose
2. **Use inheritance**: Share common configuration via base profiles
3. **Document scope and goals**: Help the agent understand its boundaries
4. **Be specific with permissions**: Only whitelist what's needed
5. **Include relevant references**: Provide context the agent needs
6. **Version your profiles**: Keep track of changes to profile configurations

## Example: Creating a New Profile

1. Create a profile folder:
   ```bash
   mkdir -p profiles/my_assistant
   ```

2. Create `profile.json`:
   ```json
   {
     "name": "my_assistant",
     "description": "My custom assistant",
     "plugins": ["cli", "todo"]
   }
   ```

3. Create `system_prompt.md`:
   ```markdown
   # My Assistant

   You are a helpful assistant specialized in...
   ```

4. Optionally add permissions, references, and plugin configs

5. Use the profile:
   ```python
   client.configure_from_profile("./profiles/my_assistant")
   ```
