#!/usr/bin/env python3
"""
AWS Cost Overview Script
Provides a comprehensive overview of current AWS costs and optimization opportunities.

This module now serves as a thin wrapper around the overview package.
All functionality has been moved to cost_toolkit/overview/ for better organization.
"""

from cost_toolkit.overview.cli import main

if __name__ == "__main__":  # pragma: no cover - script entry point
    main()
