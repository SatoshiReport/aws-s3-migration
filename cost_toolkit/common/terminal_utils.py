"""
Shared terminal utilities.

This module provides common terminal operations
to eliminate duplicate terminal handling code across scripts.
"""

import os
import subprocess


def clear_screen():
    """
    Clear the terminal screen in a cross-platform manner.

    Attempts to use the appropriate clear command for the OS,
    falling back to an ANSI escape sequence if needed.
    """
    try:
        if os.name == "nt":
            subprocess.run(["cmd", "/c", "cls"], check=False)
        else:
            subprocess.run(["clear"], check=False)
    except FileNotFoundError:
        print("\033c", end="")
