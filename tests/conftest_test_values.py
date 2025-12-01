"""Shared test constants for data integrity compliance.

This module defines all literal test values to ensure consistency
across test files and prevent data integrity violations.
"""

# Database and cache test values
TEST_MAX_ROWID = 500
TEST_MIN_SIZE_BYTES = 1024
TEST_LARGE_VOLUME_SIZE_GIB = 16384

# CPU metrics test values
TEST_MAX_CPU_PERCENT = 25.0

# Time-based test values
TEST_MINUTE_HALF_HOUR = 30

# Count test values
TEST_EFS_MOUNT_TARGET_COUNT_SMALL = 2
TEST_EFS_MOUNT_TARGET_COUNT_MEDIUM = 3
TEST_EFS_MOUNT_TARGET_COUNT_LARGE = 4
TEST_EFS_FILESYSTEM_COUNT = 2
TEST_LAMBDA_CALL_COUNT = 2
TEST_SECURITY_GROUP_COUNT = 2
TEST_UNATTACHED_VOLUME_COUNT = 2
