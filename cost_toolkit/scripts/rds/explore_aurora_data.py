#!/usr/bin/env python3
"""Explore Aurora database data."""


import psycopg2  # type: ignore[import-not-found]

# Constants
MAX_SAMPLE_COLUMNS = 5


def _list_databases(cursor):
    """List all non-template databases"""
    print("\n🗄️  AVAILABLE DATABASES:")
    cursor.execute("SELECT datname FROM pg_database WHERE datistemplate = false ORDER BY datname;")
    databases = cursor.fetchall()
    for db in databases:
        print(f"   • {db[0]}")


def _list_schemas(cursor):
    """List all user schemas"""
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


def _list_tables(cursor):
    """List all user tables"""
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
        print("   ❌ No user tables found - Aurora cluster appears to be empty")

    return tables


def _list_views(cursor):
    """List all user views"""
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
        print("   ❌ No user views found")


def _show_table_columns(cursor, schema_name, table_name):
    """Show column structure for a table"""
    cursor.execute(
        """
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


def _show_sample_data(cursor, schema_name, table_name):
    """Show sample data from a table"""
    cursor.execute(f'SELECT * FROM "{schema_name}"."{table_name}" LIMIT 2;')
    sample_data = cursor.fetchall()
    if sample_data:
        print("     Sample data:")
        col_names = [desc[0] for desc in cursor.description]
        for i, row in enumerate(sample_data, 1):
            print(f"       Row {i}: {dict(zip(col_names, row))}")
    print()


def _analyze_tables(cursor, tables):
    """Analyze table data"""
    if not tables:
        print("\n📈 SUMMARY:")
        print("   🚨 Aurora Serverless v2 cluster is EMPTY - no user data found")
        print("   💡 This means your original data is still in the restored RDS instance")
        return 0

    print("\n📊 TABLE DATA ANALYSIS:")
    total_rows = 0

    for schema_name, table_name, _ in tables:
        try:
            cursor.execute(f'SELECT COUNT(*) FROM "{schema_name}"."{table_name}";')
            count = cursor.fetchone()[0]
            total_rows += count
            print(f"   • {schema_name}.{table_name}: {count:,} rows")

            if count > 0:
                _show_table_columns(cursor, schema_name, table_name)
                _show_sample_data(cursor, schema_name, table_name)

        except Exception as e:  # pylint: disable=broad-exception-caught
            print(f"   • {schema_name}.{table_name}: Error reading - {e}")

    print("\n📈 SUMMARY:")
    print(f"   Total Tables: {len(tables)}")
    print(f"   Total Rows: {total_rows:,}")
    return total_rows


def _list_functions(cursor):
    """List all user functions and procedures"""
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
        print("   ❌ No user functions found")


def explore_aurora_database():
    """Connect to the Aurora Serverless v2 cluster and explore user data"""

    # Connection to Aurora Serverless v2 cluster
    host = "simba-db-aurora-serverless.cluster-cx5li9mlv1tt.us-east-1.rds.amazonaws.com"
    port = 5432
    database = "postgres"
    username = "postgres"
    password = "Pizza112!"

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
        return

    cursor = conn.cursor()

    print("\n📊 AURORA SERVERLESS V2 DATABASE INFORMATION:")
    cursor.execute("SELECT version();")
    version = cursor.fetchone()[0]
    print(f"   PostgreSQL Version: {version}")

    cursor.execute("SELECT current_database();")
    current_db = cursor.fetchone()[0]
    print(f"   Current Database: {current_db}")

    _list_databases(cursor)
    _list_schemas(cursor)
    tables = _list_tables(cursor)
    _list_views(cursor)
    _ = _analyze_tables(cursor, tables)

    print("\n💾 DATABASE SIZE:")
    cursor.execute("SELECT pg_size_pretty(pg_database_size(current_database())) as size;")
    db_size = cursor.fetchone()[0]
    print(f"   Database Size: {db_size}")

    _list_functions(cursor)

    cursor.close()
    conn.close()

    print("\n✅ Aurora Serverless v2 exploration completed!")

    if not tables:
        print("\n🔄 NEXT STEPS:")
        print("   1. Your Aurora Serverless v2 cluster is empty")
        print("   2. Your original data is in the restored RDS instance")
        print("   3. We need the original password to access and migrate your data")
        print("   4. Once migrated, you can delete the expensive RDS instance")


if __name__ == "__main__":
    explore_aurora_database()
