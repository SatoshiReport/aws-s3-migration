#!/usr/bin/env python3
"""
Diagnostic script to identify migration bottlenecks.
"""
import time
import boto3
import psutil
import tempfile
from pathlib import Path

def test_network_speed():
    """Test actual download speed from S3"""
    print("="*70)
    print("NETWORK SPEED TEST")
    print("="*70)

    s3 = boto3.client('s3')

    # Get a test file from your buckets
    print("Finding a test file...")
    buckets = s3.list_buckets()['Buckets']

    test_file = None
    for bucket in buckets[:5]:  # Check first 5 buckets
        try:
            response = s3.list_objects_v2(Bucket=bucket['Name'], MaxKeys=10)
            if 'Contents' in response:
                # Find a file between 1-5 MB
                for obj in response['Contents']:
                    size = obj['Size']
                    if 1_000_000 < size < 5_000_000:
                        test_file = {
                            'bucket': bucket['Name'],
                            'key': obj['Key'],
                            'size': size
                        }
                        break
            if test_file:
                break
        except Exception:
            continue

    if not test_file:
        print("Could not find suitable test file (1-5MB)")
        return None

    print(f"Test file: {test_file['bucket']}/{test_file['key']}")
    print(f"Size: {test_file['size'] / 1_000_000:.2f} MB\n")

    # Download test file
    with tempfile.NamedTemporaryFile(delete=True) as tmp:
        start = time.time()

        s3.download_file(
            Bucket=test_file['bucket'],
            Key=test_file['key'],
            Filename=tmp.name
        )

        elapsed = time.time() - start

    speed_mbps = (test_file['size'] * 8) / elapsed / 1_000_000
    speed_mbs = test_file['size'] / elapsed / 1_000_000

    print(f"Download time: {elapsed:.2f} seconds")
    print(f"Speed: {speed_mbs:.2f} MB/s ({speed_mbps:.2f} Mbps)")

    return speed_mbps

def check_system_resources():
    """Check CPU, memory, disk"""
    print("\n" + "="*70)
    print("SYSTEM RESOURCES")
    print("="*70)

    # CPU
    cpu_percent = psutil.cpu_percent(interval=1)
    cpu_count = psutil.cpu_count()
    print(f"CPU Usage: {cpu_percent}% ({cpu_count} cores)")

    # Memory
    mem = psutil.virtual_memory()
    print(f"Memory: {mem.used / (1024**3):.1f} GB / {mem.total / (1024**3):.1f} GB ({mem.percent}%)")

    # Disk
    disk = psutil.disk_usage('/Volumes/Extreme SSD')
    print(f"Disk: {disk.used / (1024**3):.1f} GB / {disk.total / (1024**3):.1f} GB ({disk.percent}%)")
    print(f"Disk Free: {disk.free / (1024**3):.1f} GB")

    # Network
    net = psutil.net_io_counters()
    print(f"\nNetwork Stats:")
    print(f"  Bytes sent: {net.bytes_sent / (1024**3):.2f} GB")
    print(f"  Bytes received: {net.bytes_recv / (1024**3):.2f} GB")

def check_file_sizes():
    """Check actual file size distribution"""
    print("\n" + "="*70)
    print("FILE SIZE ANALYSIS")
    print("="*70)

    import sqlite3
    conn = sqlite3.connect('s3_migration_state.db')

    # Get size distribution
    cursor = conn.execute("""
        SELECT
            CASE
                WHEN size < 1024 THEN '< 1 KB'
                WHEN size < 10240 THEN '1-10 KB'
                WHEN size < 102400 THEN '10-100 KB'
                WHEN size < 1048576 THEN '100 KB - 1 MB'
                WHEN size < 10485760 THEN '1-10 MB'
                WHEN size < 104857600 THEN '10-100 MB'
                ELSE '> 100 MB'
            END as size_range,
            COUNT(*) as count,
            SUM(size) as total_size
        FROM files
        WHERE state = 'discovered'
        GROUP BY size_range
        ORDER BY
            CASE size_range
                WHEN '< 1 KB' THEN 1
                WHEN '1-10 KB' THEN 2
                WHEN '10-100 KB' THEN 3
                WHEN '100 KB - 1 MB' THEN 4
                WHEN '1-10 MB' THEN 5
                WHEN '10-100 MB' THEN 6
                ELSE 7
            END
    """)

    print(f"{'Size Range':<20} {'Files':>15} {'Total Size':>15} {'% of Files':>12}")
    print("-"*70)

    total_files = 0
    for row in cursor:
        size_range, count, total_size = row
        total_files += count

    cursor = conn.execute("""
        SELECT
            CASE
                WHEN size < 1024 THEN '< 1 KB'
                WHEN size < 10240 THEN '1-10 KB'
                WHEN size < 102400 THEN '10-100 KB'
                WHEN size < 1048576 THEN '100 KB - 1 MB'
                WHEN size < 10485760 THEN '1-10 MB'
                WHEN size < 104857600 THEN '10-100 MB'
                ELSE '> 100 MB'
            END as size_range,
            COUNT(*) as count,
            SUM(size) as total_size
        FROM files
        WHERE state = 'discovered'
        GROUP BY size_range
        ORDER BY
            CASE size_range
                WHEN '< 1 KB' THEN 1
                WHEN '1-10 KB' THEN 2
                WHEN '10-100 KB' THEN 3
                WHEN '100 KB - 1 MB' THEN 4
                WHEN '1-10 MB' THEN 5
                WHEN '10-100 MB' THEN 6
                ELSE 7
            END
    """)

    for row in cursor:
        size_range, count, total_size = row
        pct = (count / total_files * 100) if total_files > 0 else 0
        size_str = f"{total_size / (1024**3):.2f} GB"
        print(f"{size_range:<20} {count:>15,} {size_str:>15} {pct:>11.1f}%")

    conn.close()

def check_active_connections():
    """Check how many S3 connections are actually active"""
    print("\n" + "="*70)
    print("NETWORK CONNECTIONS")
    print("="*70)

    try:
        connections = psutil.net_connections(kind='inet')

        # Count connections to AWS
        aws_connections = [c for c in connections if c.status == 'ESTABLISHED' and c.raddr]
        s3_connections = [c for c in aws_connections if 's3' in str(c.raddr) or 'amazonaws' in str(c.raddr)]

        print(f"Total established connections: {len(aws_connections)}")
        print(f"S3/AWS connections: {len(s3_connections)}")

        if len(s3_connections) < 50:
            print(f"\n⚠️  WARNING: Only {len(s3_connections)} S3 connections active!")
            print(f"   Expected: ~100 with current worker setting")
    except (PermissionError, psutil.AccessDenied):
        print("⚠️  Cannot check connections (macOS permissions required)")
        print("   Run with sudo if you need connection stats")
        print("   This is not critical - migration will work fine")

def main():
    print("\nS3 MIGRATION SPEED DIAGNOSTICS")
    print("="*70)
    print()

    # Run all diagnostics
    network_speed = test_network_speed()
    check_system_resources()
    check_file_sizes()
    check_active_connections()

    # Summary
    print("\n" + "="*70)
    print("DIAGNOSIS SUMMARY")
    print("="*70)

    if network_speed and network_speed < 10:
        print("❌ SLOW NETWORK: Your download speed is very slow")
        print(f"   Measured: {network_speed:.1f} Mbps")
        print(f"   This is the PRIMARY BOTTLENECK")
        print(f"\n   Solutions:")
        print(f"   1. Check if other devices are using bandwidth")
        print(f"   2. Run from faster network location")
        print(f"   3. Consider running from AWS EC2 instance")
    elif network_speed and network_speed < 50:
        print("⚠️  MODERATE NETWORK: Your network could be faster")
        print(f"   Measured: {network_speed:.1f} Mbps")
    else:
        print("✓ Network speed looks OK")

    print("\nRun this diagnostic periodically to monitor performance.")

if __name__ == "__main__":
    main()
