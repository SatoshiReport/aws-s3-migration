#!/usr/bin/env python3
"""Quick state check"""
import sqlite3

conn = sqlite3.connect('s3_migration_state.db')

cursor = conn.execute("""
    SELECT state, COUNT(*) as count, SUM(size) as total_size
    FROM files
    GROUP BY state
    ORDER BY count DESC
""")

print("\nFile States:")
print(f"{'State':<30} {'Count':>15} {'Size':>15}")
print("-" * 65)

for row in cursor:
    state, count, size = row
    size_gb = (size or 0) / (1024**3)
    print(f"{state:<30} {count:>15,} {size_gb:>14.2f} GB")

print("\nTotal files in database:")
cursor = conn.execute("SELECT COUNT(*) FROM files")
print(f"  {cursor.fetchone()[0]:,} files")

conn.close()
