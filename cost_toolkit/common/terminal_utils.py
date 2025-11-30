"""Shared terminal utilities for CLI scripts."""


def clear_screen():
    """Clear the terminal screen without shelling out to the OS."""
    print("\033[2J\033[H", end="", flush=True)
