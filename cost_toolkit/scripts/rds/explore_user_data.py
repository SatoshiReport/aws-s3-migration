#!/usr/bin/env python3
"""Explore RDS user data and credentials."""


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
        return

    host = "simba-db-restored.cx5li9mlv1tt.us-east-1.rds.amazonaws.com"
    port = 5432
    username = "postgres"
    possible_passwords = [
        "wurpov-nepqIc-puwdy9",
        "Pizza112!",
        "TempPassword123!",
        "postgres",
        "password",
        "admin",
    ]
    possible_databases = ["postgres", "simba", "simba_db", "template1"]

    print("🔍 Connecting to restored RDS instance (contains your original data)...")

    conn, _database = _try_database_connection(
        host, port, possible_databases, username, possible_passwords
    )

    if not conn:
        print("❌ Could not connect with any combination")
        print("Please check the database configuration")
        return

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


def main():
    """Main function."""
    explore_restored_database()


if __name__ == "__main__":
    main()
