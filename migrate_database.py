#!/usr/bin/env python3
"""
Migrate existing migration database to V2 schema.
Preserves all existing data (3.9M scanned files).
"""
import sqlite3
import json
from datetime import datetime, timezone

DB_PATH = "s3_migration_state.db"


def migrate_database():
    """Upgrade database schema to V2"""
    print("\n" + "="*70)
    print("DATABASE MIGRATION: V1 → V2")
    print("="*70)
    print()

    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        # Check if files table exists
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='files'
        """)
        if not cursor.fetchone():
            print("No existing database found - V2 will create fresh database")
            return

        print("Found existing database with files")

        # Get current file count
        cursor.execute("SELECT COUNT(*) as count FROM files")
        file_count = cursor.fetchone()['count']
        print(f"  Files in database: {file_count:,}")
        print()

        # 1. Add new columns to files table if they don't exist
        print("Step 1: Adding new columns to files table...")

        # Check which columns exist
        cursor.execute("PRAGMA table_info(files)")
        existing_columns = {row['name'] for row in cursor.fetchall()}

        new_columns = {
            'local_checksum': 'TEXT',
            'glacier_restored_at': 'TEXT'
        }

        for col_name, col_type in new_columns.items():
            if col_name not in existing_columns:
                cursor.execute(f"ALTER TABLE files ADD COLUMN {col_name} {col_type}")
                print(f"  ✓ Added column: {col_name}")
            else:
                print(f"  - Column exists: {col_name}")

        print()

        # 2. Create bucket_status table
        print("Step 2: Creating bucket_status table...")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bucket_status (
                bucket TEXT PRIMARY KEY,
                file_count INTEGER NOT NULL,
                total_size INTEGER NOT NULL,
                storage_class_counts TEXT,
                scan_complete BOOLEAN DEFAULT 0,
                sync_complete BOOLEAN DEFAULT 0,
                verify_complete BOOLEAN DEFAULT 0,
                delete_complete BOOLEAN DEFAULT 0,
                local_file_count INTEGER,
                local_total_size INTEGER,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        print("  ✓ Created bucket_status table")
        print()

        # 3. Populate bucket_status from existing files
        print("Step 3: Populating bucket_status from existing files...")

        cursor.execute("""
            SELECT
                bucket,
                COUNT(*) as file_count,
                SUM(size) as total_size,
                storage_class
            FROM files
            GROUP BY bucket, storage_class
        """)

        # Aggregate by bucket
        bucket_data = {}
        for row in cursor.fetchall():
            bucket = row['bucket']
            if bucket not in bucket_data:
                bucket_data[bucket] = {
                    'file_count': 0,
                    'total_size': 0,
                    'storage_classes': {}
                }

            bucket_data[bucket]['file_count'] += row['file_count']
            bucket_data[bucket]['total_size'] += row['total_size'] or 0
            storage_class = row['storage_class'] or 'STANDARD'
            bucket_data[bucket]['storage_classes'][storage_class] = \
                bucket_data[bucket]['storage_classes'].get(storage_class, 0) + row['file_count']

        # Insert bucket_status records
        now = datetime.now(timezone.utc).isoformat()
        for bucket, data in bucket_data.items():
            storage_json = json.dumps(data['storage_classes'])
            cursor.execute("""
                INSERT OR REPLACE INTO bucket_status
                (bucket, file_count, total_size, storage_class_counts,
                 scan_complete, created_at, updated_at)
                VALUES (?, ?, ?, ?, 1, ?, ?)
            """, (bucket, data['file_count'], data['total_size'],
                  storage_json, now, now))

        print(f"  ✓ Created status for {len(bucket_data)} bucket(s)")
        print()

        # 4. Set initial phase based on existing state
        print("Step 4: Setting initial phase...")

        # Check if any files are deleted (migration in progress)
        cursor.execute("SELECT COUNT(*) as count FROM files WHERE state = 'deleted'")
        deleted_count = cursor.fetchone()['count']

        # Check if any files are in discovered state
        cursor.execute("SELECT COUNT(*) as count FROM files WHERE state = 'discovered'")
        discovered_count = cursor.fetchone()['count']

        if deleted_count > 0 and discovered_count > 0:
            # Migration was in progress - need to sync remaining files
            print("  Migration was in progress")
            print(f"    Completed: {deleted_count:,} files")
            print(f"    Remaining: {discovered_count:,} files")
            print("  Setting phase to: syncing")
            initial_phase = 'syncing'
        elif discovered_count > 0:
            # Scanning complete, need to check for Glacier
            print("  Scanning was complete")
            print(f"    Files scanned: {discovered_count:,}")

            # Check for Glacier files
            cursor.execute("""
                SELECT COUNT(*) as count FROM files
                WHERE storage_class IN ('GLACIER', 'DEEP_ARCHIVE')
                AND glacier_restore_requested_at IS NULL
            """)
            glacier_count = cursor.fetchone()['count']

            if glacier_count > 0:
                print(f"    Glacier files: {glacier_count:,}")
                print("  Setting phase to: glacier_restore")
                initial_phase = 'glacier_restore'
            else:
                print("  Setting phase to: syncing")
                initial_phase = 'syncing'
        else:
            print("  Setting phase to: scanning")
            initial_phase = 'scanning'

        cursor.execute("""
            INSERT OR REPLACE INTO migration_metadata
            (key, value, updated_at)
            VALUES ('current_phase', ?, ?)
        """, (initial_phase, now))

        print()

        # 5. Create new indices
        print("Step 5: Creating indices...")
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_files_bucket
            ON files(bucket)
        """)
        print("  ✓ Created index on bucket")
        print()

        # Commit all changes
        conn.commit()

        print("="*70)
        print("✓ DATABASE MIGRATION COMPLETE")
        print("="*70)
        print()
        print("Your existing data has been preserved:")
        print(f"  Files: {file_count:,}")
        print(f"  Buckets: {len(bucket_data)}")
        print()
        print("You can now run: python migrate_v2.py")
        print("="*70)
        print()

    except Exception as e:
        conn.rollback()
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        print("\nDatabase migration failed - please report this error")

    finally:
        conn.close()


if __name__ == "__main__":
    migrate_database()
