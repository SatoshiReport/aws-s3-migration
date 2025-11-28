#!/usr/bin/env python3
"""Explore RDS user data and credentials."""


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
DEFAULT_RESTORED_HOST = os.environ.get("RESTORED_DB_HOST", "restored-db.example.com")
DEFAULT_RESTORED_PORT = int(os.environ.get("RESTORED_DB_PORT", "5432"))
DEFAULT_RESTORED_USERNAME = os.environ.get("RESTORED_DB_USERNAME", "postgres")
DEFAULT_DB_NAMES = (
    os.environ.get("RESTORED_DB_NAMES", "postgres,template1").split(",")
)
DEFAULT_PASSWORDS = os.environ.get("RESTORED_DB_PASSWORDS", "postgres,password,admin").split(",")


def _load_restored_db_settings():
    """Load restored DB connection settings from environment variables."""
    host = os.environ.get("RESTORED_DB_HOST", DEFAULT_RESTORED_HOST)
    port = int(os.environ.get("RESTORED_DB_PORT", DEFAULT_RESTORED_PORT))
    username = os.environ.get("RESTORED_DB_USERNAME", DEFAULT_RESTORED_USERNAME)
    databases = [
        db.strip() for db in os.environ.get("RESTORED_DB_NAMES", ",".join(DEFAULT_DB_NAMES)).split(",") if db.strip()
    ]
    passwords = [
        pw.strip()
        for pw in os.environ.get("RESTORED_DB_PASSWORDS", ",".join(DEFAULT_PASSWORDS)).split(",")
        if pw.strip()
    ]
    return host, port, databases, username, passwords


def _try_database_connection(host, port, possible_databases, username, possible_passwords):
    """Try connecting with different database and password combinations"""
    for db_name in possible_databases:
        for password in possible_passwords:
            try:
                print(f"   Trying database='{db_name}' with password='{password[:10]}...'")
                conn = psycopg2.connect(
                    host=host,
                    port=port,
                    database=db_name,
                    user=username,
                    password=password,
                    connect_timeout=15,
                )
                print("✅ Connected successfully!")
                print(f"   Database: {db_name}")
                print(f"   Password: {password[:10]}...")
            except psycopg2.Error as e:
                print(f"   ❌ Failed: {str(e)[:80]}...")
                continue
            else:
                return conn, db_name
    return None, None


def explore_restored_database():
    """Connect to the restored RDS instance and explore user data"""
    if not PSYCOPG2_AVAILABLE:
        print("❌ psycopg2 module not found. Install with: pip install psycopg2-binary")
        return False

    host, port, possible_databases, username, possible_passwords = _load_restored_db_settings()

    print("🔍 Connecting to restored RDS instance (contains your original data)...")

    conn, _database = _try_database_connection(
        host, port, possible_databases, username, possible_passwords
    )

    if not conn:
        print("❌ Could not connect with any combination")
        print("Please check the database configuration")
        return False

    cursor = conn.cursor()

    print("\n📊 DATABASE INFORMATION:")
    print_database_version_info(cursor)

    list_databases(cursor)
    list_schemas(cursor)
    tables = list_tables(cursor)
    list_views(cursor)
    analyze_tables(cursor, tables, MAX_SAMPLE_COLUMNS)

    get_database_size(cursor)

    list_functions(cursor)

    cursor.close()
    conn.close()

    print("\n✅ Database exploration completed!")
    return True


def main():
    """Main function."""
    success = explore_restored_database()
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
