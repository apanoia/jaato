#!/usr/bin/env python3
"""Test script to observe MCP plugin lifecycle behavior."""

import time
from shared.plugins.mcp.plugin import create_plugin

def main():
    print("Creating MCP plugin...")
    plugin = create_plugin()

    print("Initializing plugin...")
    plugin.initialize()

    print("Sleeping for 2 seconds...")
    time.sleep(2)

    # Check if thread is still alive
    if plugin._thread and plugin._thread.is_alive():
        print(f"✓ Background thread is ALIVE (id: {plugin._thread.ident})")
    else:
        print("✗ Background thread is DEAD")

    print("\nCalling get_tool_schemas() 5 times with 1s intervals...")
    for i in range(5):
        print(f"\n--- Call {i+1} ---")
        thread_before = plugin._thread.ident if plugin._thread else None
        print(f"Thread ID before: {thread_before}")

        schemas = plugin.get_tool_schemas()
        print(f"Got {len(schemas)} tool schemas")

        thread_after = plugin._thread.ident if plugin._thread else None
        print(f"Thread ID after: {thread_after}")

        if thread_before != thread_after:
            print("⚠️  THREAD ID CHANGED! Connection cycling detected!")

        time.sleep(1)

    print("\nFinal thread check...")
    if plugin._thread and plugin._thread.is_alive():
        print(f"✓ Background thread still alive (id: {plugin._thread.ident})")
    else:
        print("✗ Background thread died")

    print("\nShutting down...")
    plugin.shutdown()

if __name__ == "__main__":
    main()
