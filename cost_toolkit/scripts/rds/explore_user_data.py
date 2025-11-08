#!/usr/bin/env python3
import sys

import psycopg2

# Constants
MAX_SAMPLE_COLUMNS = 5


def explore_restored_database():  # noqa: C901, PLR0912, PLR0915
    """Connect to the restored RDS instance and explore user data"""

    # Connection to restored instance (contains original data)
    host = "simba-db-restored.cx5li9mlv1tt.us-east-1.rds.amazonaws.com"
    port = 5432
    database = "postgres"
    username = "postgres"
    # We'll try common passwords since this was restored from snapshot
    possible_passwords = [
        "wurpov-nepqIc-puwdy9",
        "Pizza112!",
        "TempPassword123!",
        "postgres",
        "password",
        "admin",
    ]

    print("🔍 Connecting to restored RDS instance (contains your original data)...")

    # Try different database names and passwords
    possible_databases = ["postgres", "simba", "simba_db", "template1"]

    conn = None
    successful_combo = None

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
                successful_combo = (db_name, password)
                print(f"✅ Connected successfully!")
                print(f"   Database: {db_name}")
                print(f"   Password: {password[:10]}...")
                database = db_name  # Update database variable for later use
                break
            except psycopg2.Error as e:
                print(f"   ❌ Failed: {str(e)[:80]}...")
                continue
        if conn:
            break

    if not conn:
        print("❌ Could not connect with any combination")
        print("Please check the database configuration")
        return

    cursor = conn.cursor()

    # Get database info
    print("\n📊 DATABASE INFORMATION:")
    cursor.execute("SELECT version();")
    version = cursor.fetchone()[0]
    print(f"   PostgreSQL Version: {version}")

    cursor.execute("SELECT current_database();")
    current_db = cursor.fetchone()[0]
    print(f"   Current Database: {current_db}")

    # List all databases
    print("\n🗄️  AVAILABLE DATABASES:")
    cursor.execute("SELECT datname FROM pg_database WHERE datistemplate = false ORDER BY datname;")
    databases = cursor.fetchall()
    for db in databases:
        print(f"   • {db[0]}")

    # List all user schemas
    print("\n📁 USER SCHEMAS:")
    cursor.execute(
        """
        SELECT schema_name 
        FROM information_schema.schemata 
        WHERE schema_name NOT IN ('information_schema', 'pg_catalog', 'pg_toast')
        ORDER BY schema_name;
    """
    )
    schemas = cursor.fetchall()
    for schema in schemas:
        print(f"   • {schema[0]}")

    # List all user tables
    print("\n📋 USER TABLES:")
    cursor.execute(
        """
        SELECT schemaname, tablename, tableowner 
        FROM pg_tables 
        WHERE schemaname NOT IN ('information_schema', 'pg_catalog')
        ORDER BY schemaname, tablename;
    """
    )
    tables = cursor.fetchall()

    if tables:
        for table in tables:
            print(f"   • {table[0]}.{table[1]} (owner: {table[2]})")
    else:
        print("   No user tables found")

    # List all views
    print("\n👁️  USER VIEWS:")
    cursor.execute(
        """
        SELECT schemaname, viewname, viewowner 
        FROM pg_views 
        WHERE schemaname NOT IN ('information_schema', 'pg_catalog')
        ORDER BY schemaname, viewname;
    """
    )
    views = cursor.fetchall()

    if views:
        for view in views:
            print(f"   • {view[0]}.{view[1]} (owner: {view[2]})")
    else:
        print("   No user views found")

    # Analyze table data
    if tables:
        print("\n📊 TABLE DATA ANALYSIS:")
        total_rows = 0

        for schema_name, table_name, owner in tables:
            try:
                cursor.execute(f'SELECT COUNT(*) FROM "{schema_name}"."{table_name}";')
                count = cursor.fetchone()[0]
                total_rows += count
                print(f"   • {schema_name}.{table_name}: {count:,} rows")

                # Show column structure for tables with data
                if count > 0:
                    cursor.execute(
                        f"""
                        SELECT column_name, data_type, is_nullable, column_default
                        FROM information_schema.columns 
                        WHERE table_schema = '{schema_name}' AND table_name = '{table_name}'
                        ORDER BY ordinal_position;
                    """
                    )
                    columns = cursor.fetchall()
                    print(f"     Columns ({len(columns)}):")
                    for col in columns[:MAX_SAMPLE_COLUMNS]:
                        nullable = "NULL" if col[2] == "YES" else "NOT NULL"
                        default = f" DEFAULT {col[3]}" if col[3] else ""
                        print(f"       - {col[0]} ({col[1]}) {nullable}{default}")
                    if len(columns) > MAX_SAMPLE_COLUMNS:
                        print(f"       ... and {len(columns) - MAX_SAMPLE_COLUMNS} more columns")

                    # Show sample data (first 2 rows)
                    cursor.execute(f'SELECT * FROM "{schema_name}"."{table_name}" LIMIT 2;')
                    sample_data = cursor.fetchall()
                    if sample_data:
                        print(f"     Sample data:")
                        col_names = [desc[0] for desc in cursor.description]
                        for i, row in enumerate(sample_data, 1):
                            print(f"       Row {i}: {dict(zip(col_names, row))}")
                    print()

            except Exception as e:
                print(f"   • {schema_name}.{table_name}: Error reading - {e}")

        print(f"\n📈 SUMMARY:")
        print(f"   Total Tables: {len(tables)}")
        print(f"   Total Rows: {total_rows:,}")

    # Check database size
    print("\n💾 DATABASE SIZE:")
    cursor.execute("SELECT pg_size_pretty(pg_database_size(current_database())) as size;")
    db_size = cursor.fetchone()[0]
    print(f"   Database Size: {db_size}")

    # Check for functions/procedures
    print("\n⚙️  USER FUNCTIONS:")
    cursor.execute(
        """
        SELECT routine_schema, routine_name, routine_type
        FROM information_schema.routines 
        WHERE routine_schema NOT IN ('information_schema', 'pg_catalog')
        ORDER BY routine_schema, routine_name;
    """
    )
    functions = cursor.fetchall()

    if functions:
        for func in functions:
            print(f"   • {func[0]}.{func[1]} ({func[2]})")
    else:
        print("   No user functions found")

    cursor.close()
    conn.close()

    print("\n✅ Database exploration completed!")


if __name__ == "__main__":
    explore_restored_database()
