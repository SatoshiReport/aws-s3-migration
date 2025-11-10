#!/usr/bin/env python3
"""
AWS RDS to Aurora Serverless v2 Migration Script
Migrates existing RDS instances to Aurora Serverless v2 for cost optimization.

This is a thin wrapper around the rds_aurora_migration package.
"""

from cost_toolkit.scripts.migration.rds_aurora_migration import main

if __name__ == "__main__":
    main()
