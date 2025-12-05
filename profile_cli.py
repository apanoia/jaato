#!/usr/bin/env python3
"""CLI for managing agent profiles.

Usage:
    python profile_cli.py list [--path PATH]
    python profile_cli.py info PROFILE_NAME [--path PATH]
    python profile_cli.py validate PROFILE_PATH
    python profile_cli.py init PROFILE_PATH [--name NAME]
"""

import argparse
import json
import sys
from pathlib import Path


def cmd_list(args):
    """List all discovered profiles."""
    from shared.profiles import ProfileLoader

    loader = ProfileLoader()

    # Add search paths
    if args.path:
        for path in args.path:
            loader.add_search_path(Path(path).expanduser())
    else:
        # Default paths
        cwd_profiles = Path.cwd() / "profiles"
        if cwd_profiles.is_dir():
            loader.add_search_path(cwd_profiles)

        example_profiles = Path.cwd() / "profiles.example"
        if example_profiles.is_dir():
            loader.add_search_path(example_profiles)

    loader.add_search_paths_from_env()
    loader.discover()

    profiles = loader.list_profiles()

    if not profiles:
        print("No profiles found.")
        print("\nSearch paths:")
        for path in loader._search_paths:
            print(f"  - {path}")
        return

    print(f"Found {len(profiles)} profile(s):\n")

    for profile in profiles:
        print(f"  {profile['name']}")
        if profile.get('description'):
            print(f"    Description: {profile['description']}")
        if profile.get('tags'):
            print(f"    Tags: {', '.join(profile['tags'])}")
        if profile.get('plugins'):
            print(f"    Plugins: {', '.join(profile['plugins'])}")
        if profile.get('error'):
            print(f"    Error: {profile['error']}")
        print(f"    Path: {profile['path']}")
        print()


def cmd_info(args):
    """Show detailed information about a profile."""
    from shared.profiles import ProfileLoader, ProfileValidationError

    loader = ProfileLoader()

    # Add search paths
    if args.path:
        for path in args.path:
            loader.add_search_path(Path(path).expanduser())
    else:
        cwd_profiles = Path.cwd() / "profiles"
        if cwd_profiles.is_dir():
            loader.add_search_path(cwd_profiles)

        example_profiles = Path.cwd() / "profiles.example"
        if example_profiles.is_dir():
            loader.add_search_path(example_profiles)

    loader.add_search_paths_from_env()
    loader.discover()

    try:
        profile = loader.load(args.profile_name)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except ProfileValidationError as e:
        print(f"Validation Error: {e}")
        sys.exit(1)

    print(f"Profile: {profile.name}")
    print(f"  Description: {profile.description}")
    print(f"  Path: {profile.profile_path}")
    print()

    if profile.config.extends:
        print(f"  Extends: {profile.config.extends}")

    print(f"  Model: {profile.model or '(default)'}")
    print(f"  Max Turns: {profile.max_turns}")
    print(f"  Auto Approved: {profile.auto_approved}")
    print()

    if profile.tags:
        print(f"  Tags: {', '.join(profile.tags)}")

    if profile.config.scope:
        print(f"\n  Scope:")
        print(f"    {profile.config.scope}")

    if profile.config.goals:
        print(f"\n  Goals:")
        for goal in profile.config.goals:
            print(f"    - {goal}")

    print(f"\n  Plugins: {', '.join(profile.plugins) if profile.plugins else '(none)'}")

    if profile.plugin_configs:
        print(f"\n  Plugin Configs:")
        for name in profile.plugin_configs:
            print(f"    - {name}")

    print(f"\n  Has System Prompt: {'Yes' if profile.system_prompt else 'No'}")
    print(f"  Has Permissions: {'Yes' if profile.permissions_config else 'No'}")
    print(f"  Has References Config: {'Yes' if profile.references_config else 'No'}")

    if profile.local_references:
        print(f"\n  Local References:")
        for ref in profile.local_references:
            print(f"    - {ref.name}")

    if args.verbose and profile.system_prompt:
        print(f"\n  System Prompt Preview (first 500 chars):")
        print("  " + "-" * 40)
        preview = profile.system_prompt[:500]
        for line in preview.split('\n'):
            print(f"    {line}")
        if len(profile.system_prompt) > 500:
            print(f"    ... ({len(profile.system_prompt) - 500} more chars)")


def cmd_validate(args):
    """Validate a profile at the given path."""
    from shared.profiles import ProfileLoader, ProfileValidationError

    profile_path = Path(args.profile_path).expanduser()

    if not profile_path.is_dir():
        print(f"Error: Not a directory: {profile_path}")
        sys.exit(1)

    profile_json = profile_path / "profile.json"
    if not profile_json.exists():
        print(f"Error: Missing profile.json in {profile_path}")
        sys.exit(1)

    loader = ProfileLoader()

    try:
        profile = loader.load_from_path(profile_path)
        print(f"Profile '{profile.name}' is valid!")
        print(f"\n  Plugins: {', '.join(profile.plugins) if profile.plugins else '(none)'}")
        print(f"  Has System Prompt: {'Yes' if profile.system_prompt else 'No'}")
        print(f"  Has Permissions: {'Yes' if profile.permissions_config else 'No'}")
        print(f"  Local References: {len(profile.local_references)}")
    except ProfileValidationError as e:
        print(f"Validation failed for '{e.profile_name}':")
        for error in e.errors:
            print(f"  - {error}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"JSON parsing error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


def cmd_init(args):
    """Initialize a new profile at the given path."""
    profile_path = Path(args.profile_path).expanduser()
    name = args.name or profile_path.name

    if profile_path.exists():
        print(f"Error: Path already exists: {profile_path}")
        sys.exit(1)

    # Create directory structure
    profile_path.mkdir(parents=True)
    (profile_path / "references").mkdir()
    (profile_path / "plugin_configs").mkdir()

    # Create profile.json
    profile_config = {
        "name": name,
        "description": f"Description for {name}",
        "version": "1.0",
        "plugins": ["todo"],
        "max_turns": 20,
        "auto_approved": False,
        "tags": [],
        "scope": "Define the scope of this profile",
        "goals": [
            "Goal 1",
            "Goal 2"
        ]
    }

    with open(profile_path / "profile.json", 'w') as f:
        json.dump(profile_config, f, indent=2)

    # Create system_prompt.md
    system_prompt = f"""# {name}

You are an AI assistant configured with the {name} profile.

## Instructions

Add your system instructions here.

## Guidelines

- Guideline 1
- Guideline 2
"""
    with open(profile_path / "system_prompt.md", 'w') as f:
        f.write(system_prompt)

    print(f"Created new profile at: {profile_path}")
    print(f"\nCreated files:")
    print(f"  - profile.json")
    print(f"  - system_prompt.md")
    print(f"  - references/ (empty directory)")
    print(f"  - plugin_configs/ (empty directory)")
    print(f"\nNext steps:")
    print(f"  1. Edit profile.json to configure plugins and settings")
    print(f"  2. Edit system_prompt.md to add your instructions")
    print(f"  3. Optionally add permissions.json for access control")
    print(f"  4. Optionally add reference documents to references/")


def main():
    parser = argparse.ArgumentParser(
        description="CLI for managing agent profiles"
    )
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # list command
    list_parser = subparsers.add_parser("list", help="List discovered profiles")
    list_parser.add_argument(
        "--path", "-p",
        action="append",
        help="Additional paths to search (can be specified multiple times)"
    )

    # info command
    info_parser = subparsers.add_parser("info", help="Show profile details")
    info_parser.add_argument("profile_name", help="Name of the profile")
    info_parser.add_argument(
        "--path", "-p",
        action="append",
        help="Additional paths to search (can be specified multiple times)"
    )
    info_parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show additional details including system prompt preview"
    )

    # validate command
    validate_parser = subparsers.add_parser("validate", help="Validate a profile")
    validate_parser.add_argument("profile_path", help="Path to the profile folder")

    # init command
    init_parser = subparsers.add_parser("init", help="Initialize a new profile")
    init_parser.add_argument("profile_path", help="Path where to create the profile")
    init_parser.add_argument(
        "--name", "-n",
        help="Profile name (defaults to directory name)"
    )

    args = parser.parse_args()

    if args.command == "list":
        cmd_list(args)
    elif args.command == "info":
        cmd_info(args)
    elif args.command == "validate":
        cmd_validate(args)
    elif args.command == "init":
        cmd_init(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
