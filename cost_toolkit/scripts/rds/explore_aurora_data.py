#!/usr/bin/env python3
"""Explore Aurora database data."""

import os

try:
    import psycopg2  # type: ignore[import-not-found]

    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False

from cost_toolkit.scripts.rds.db_inspection_common import (
    analyze_tables,
    get_database_size,
    list_databases,
    list_functions,
    list_schemas,
    list_tables,
    list_views,
    print_database_version_info,
)

# Constants
MAX_SAMPLE_COLUMNS = 5


def _require_env_var(name: str) -> str:
    """Return a required environment variable or raise."""
    value = os.environ.get(name)
    if value is None or not value.strip():
        raise RuntimeError(f"{name} is required to explore the Aurora cluster")
    return value.strip()


def _parse_required_port(name: str) -> int:
    """Parse a required port environment variable."""
    raw_value = _require_env_var(name)
    try:
        return int(raw_value)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be a valid integer, got {raw_value!r}") from exc


def _load_aurora_settings():
    """Load Aurora connection settings from environment variables."""
    host = _require_env_var("AURORA_HOST")
    port = _parse_required_port("AURORA_PORT")
    database = _require_env_var("AURORA_DATABASE")
    username = _require_env_var("AURORA_USERNAME")
    password = _require_env_var("AURORA_PASSWORD")
    return host, port, database, username, password


def explore_aurora_database():
    """Connect to the Aurora Serverless v2 cluster and explore user data"""
    if not PSYCOPG2_AVAILABLE:
        print("❌ psycopg2 module not found. Install with: pip install psycopg2-binary")
        return False

    host, port, database, username, password = _load_aurora_settings()
    if not password:
        print(
            "❌ Aurora credentials not configured. "
            "Set AURORA_PASSWORD (and optionally AURORA_HOST/AURORA_DATABASE/AURORA_USERNAME)."
        )
        return False

    print("🔍 Connecting to Aurora Serverless v2 cluster...")

    try:
        conn = psycopg2.connect(
            host=host,
            port=port,
            database=database,
            user=username,
            password=password,
            connect_timeout=30,
        )
        print("✅ Connected successfully to Aurora Serverless v2!")
    except psycopg2.Error as e:
        print(f"❌ Connection failed: {e}")
        return False

    cursor = conn.cursor()

    print("\n📊 AURORA SERVERLESS V2 DATABASE INFORMATION:")
    print_database_version_info(cursor)

    list_databases(cursor)
    list_schemas(cursor)
    tables = list_tables(cursor)
    if not tables:
        print("   ❌ No user tables found - Aurora cluster appears to be empty")
    list_views(cursor)

    total_rows = analyze_tables(cursor, tables, MAX_SAMPLE_COLUMNS)

    get_database_size(cursor)

    list_functions(cursor)

    cursor.close()
    conn.close()

    print("\n✅ Aurora Serverless v2 exploration completed!")

    if total_rows == 0:
        print("\n📈 SUMMARY:")
        print("   🚨 Aurora Serverless v2 cluster is EMPTY - no user data found")
        print("   💡 This means your original data is still in the restored RDS instance")
        print("\n🔄 NEXT STEPS:")
        print("   1. Your Aurora Serverless v2 cluster is empty")
        print("   2. Your original data is in the restored RDS instance")
        print("   3. We need the original password to access and migrate your data")
        print("   4. Once migrated, you can delete the expensive RDS instance")
    return True


def main():
    """Main function."""
    success = explore_aurora_database()
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
