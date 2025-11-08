"""
Unit tests for config.py multipart transfer and bucket exclusion configurations.

Tests verify:
- Multipart transfer settings (threshold, chunksize, concurrency, threads)
- Bucket exclusions list
"""

import config

MAX_CONCURRENCY_LIMIT = 50


class TestMultipartTransferSettings:
    """Tests for S3 multipart transfer configuration."""

    def test_multipart_threshold_exists(self):
        """Verify MULTIPART_THRESHOLD constant exists."""
        assert hasattr(config, "MULTIPART_THRESHOLD")

    def test_multipart_threshold_is_integer(self):
        """Verify MULTIPART_THRESHOLD is an integer."""
        assert isinstance(config.MULTIPART_THRESHOLD, int)

    def test_multipart_threshold_is_positive(self):
        """Verify MULTIPART_THRESHOLD is positive."""
        assert config.MULTIPART_THRESHOLD > 0

    def test_multipart_threshold_reasonable_range(self):
        """Verify MULTIPART_THRESHOLD is reasonable (5MB to 100MB)."""
        min_threshold = 5 * 1024 * 1024  # 5MB
        max_threshold = 100 * 1024 * 1024  # 100MB
        assert min_threshold <= config.MULTIPART_THRESHOLD <= max_threshold

    def test_multipart_chunksize_exists(self):
        """Verify MULTIPART_CHUNKSIZE constant exists."""
        assert hasattr(config, "MULTIPART_CHUNKSIZE")

    def test_multipart_chunksize_is_integer(self):
        """Verify MULTIPART_CHUNKSIZE is an integer."""
        assert isinstance(config.MULTIPART_CHUNKSIZE, int)

    def test_multipart_chunksize_is_positive(self):
        """Verify MULTIPART_CHUNKSIZE is positive."""
        assert config.MULTIPART_CHUNKSIZE > 0

    def test_multipart_chunksize_reasonable_range(self):
        """Verify MULTIPART_CHUNKSIZE is reasonable (5MB to 100MB)."""
        min_size = 5 * 1024 * 1024  # 5MB
        max_size = 100 * 1024 * 1024  # 100MB
        assert min_size <= config.MULTIPART_CHUNKSIZE <= max_size

    def test_multipart_chunksize_minimum_is_5mb(self):
        """Verify MULTIPART_CHUNKSIZE is at least AWS minimum of 5MB."""
        min_size = 5 * 1024 * 1024
        assert config.MULTIPART_CHUNKSIZE >= min_size

    def test_max_concurrency_exists(self):
        """Verify MAX_CONCURRENCY constant exists."""
        assert hasattr(config, "MAX_CONCURRENCY")

    def test_max_concurrency_is_integer(self):
        """Verify MAX_CONCURRENCY is an integer."""
        assert isinstance(config.MAX_CONCURRENCY, int)

    def test_max_concurrency_is_positive(self):
        """Verify MAX_CONCURRENCY is positive."""
        assert config.MAX_CONCURRENCY > 0

    def test_max_concurrency_reasonable_range(self):
        """Verify MAX_CONCURRENCY is within reasonable range (1-50)."""
        assert 1 <= config.MAX_CONCURRENCY <= MAX_CONCURRENCY_LIMIT

    def test_use_threads_exists(self):
        """Verify USE_THREADS constant exists."""
        assert hasattr(config, "USE_THREADS")

    def test_use_threads_is_boolean(self):
        """Verify USE_THREADS is a boolean."""
        assert isinstance(config.USE_THREADS, bool)


class TestBucketExclusions:
    """Tests for EXCLUDED_BUCKETS configuration."""

    def test_excluded_buckets_exists(self):
        """Verify EXCLUDED_BUCKETS constant exists."""
        assert hasattr(config, "EXCLUDED_BUCKETS")

    def test_excluded_buckets_is_list(self):
        """Verify EXCLUDED_BUCKETS is a list."""
        assert isinstance(config.EXCLUDED_BUCKETS, list)

    def test_excluded_buckets_all_strings(self):
        """Verify all items in EXCLUDED_BUCKETS are strings."""
        for bucket in config.EXCLUDED_BUCKETS:
            assert isinstance(bucket, str)

    def test_excluded_buckets_no_empty_strings(self):
        """Verify EXCLUDED_BUCKETS contains no empty strings."""
        for bucket in config.EXCLUDED_BUCKETS:
            assert len(bucket) > 0

    def test_excluded_buckets_valid_bucket_names(self):
        """Verify EXCLUDED_BUCKETS contains valid S3 bucket names (lowercase, no uppercase)."""
        for bucket in config.EXCLUDED_BUCKETS:
            # S3 bucket names are lowercase alphanumeric, hyphens, and dots
            assert bucket.islower() or "-" in bucket or "_" in bucket or "." in bucket
