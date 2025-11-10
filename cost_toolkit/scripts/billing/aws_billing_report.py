#!/usr/bin/env python3
"""
AWS Billing Report Script
Gets detailed billing information for the past month including services, regions, and costs.

This module serves as a backward-compatible entry point to the billing_report package.
"""

from cost_toolkit.scripts.billing.billing_report import main

if __name__ == "__main__":
    main()
