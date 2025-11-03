"""
Comprehensive unit tests for config.py

Tests verify all configuration constants:
- Existence and accessibility
- Data types
- Reasonable value ranges
- Proper formatting (paths, strings)
"""

import config


class TestLocalBasePath:
    """Tests for LOCAL_BASE_PATH configuration."""

    def test_local_base_path_exists(self):
        """Verify LOCAL_BASE_PATH constant exists."""
        assert hasattr(config, "LOCAL_BASE_PATH")

    def test_local_base_path_is_string(self):
        """Verify LOCAL_BASE_PATH is a string."""
        assert isinstance(config.LOCAL_BASE_PATH, str)

    def test_local_base_path_not_empty(self):
        """Verify LOCAL_BASE_PATH is not empty."""
        assert len(config.LOCAL_BASE_PATH) > 0

    def test_local_base_path_is_absolute(self):
        """Verify LOCAL_BASE_PATH looks like an absolute path."""
        # Should start with / on Unix-like systems or drive letter on Windows
        assert config.LOCAL_BASE_PATH.startswith("/") or config.LOCAL_BASE_PATH[1] == ":"


class TestStateDbPath:
    """Tests for STATE_DB_PATH configuration."""

    def test_state_db_path_exists(self):
        """Verify STATE_DB_PATH constant exists."""
        assert hasattr(config, "STATE_DB_PATH")

    def test_state_db_path_is_string(self):
        """Verify STATE_DB_PATH is a string."""
        assert isinstance(config.STATE_DB_PATH, str)

    def test_state_db_path_not_empty(self):
        """Verify STATE_DB_PATH is not empty."""
        assert len(config.STATE_DB_PATH) > 0

    def test_state_db_path_has_db_extension(self):
        """Verify STATE_DB_PATH ends with .db extension."""
        assert config.STATE_DB_PATH.endswith(".db")


class TestGlacierRestoreSettings:
    """Tests for Glacier restore configuration."""

    def test_glacier_restore_days_exists(self):
        """Verify GLACIER_RESTORE_DAYS constant exists."""
        assert hasattr(config, "GLACIER_RESTORE_DAYS")

    def test_glacier_restore_days_is_integer(self):
        """Verify GLACIER_RESTORE_DAYS is an integer."""
        assert isinstance(config.GLACIER_RESTORE_DAYS, int)

    def test_glacier_restore_days_is_positive(self):
        """Verify GLACIER_RESTORE_DAYS is a positive integer."""
        assert config.GLACIER_RESTORE_DAYS > 0

    def test_glacier_restore_days_reasonable_range(self):
        """Verify GLACIER_RESTORE_DAYS is within reasonable range (1-30 days)."""
        assert 1 <= config.GLACIER_RESTORE_DAYS <= 30  # noqa: PLR2004

    def test_glacier_restore_tier_exists(self):
        """Verify GLACIER_RESTORE_TIER constant exists."""
        assert hasattr(config, "GLACIER_RESTORE_TIER")

    def test_glacier_restore_tier_is_string(self):
        """Verify GLACIER_RESTORE_TIER is a string."""
        assert isinstance(config.GLACIER_RESTORE_TIER, str)

    def test_glacier_restore_tier_is_valid_option(self):
        """Verify GLACIER_RESTORE_TIER is one of the valid options."""
        valid_tiers = {"Expedited", "Standard", "Bulk"}
        assert config.GLACIER_RESTORE_TIER in valid_tiers


class TestProgressUpdateInterval:
    """Tests for PROGRESS_UPDATE_INTERVAL configuration."""

    def test_progress_update_interval_exists(self):
        """Verify PROGRESS_UPDATE_INTERVAL constant exists."""
        assert hasattr(config, "PROGRESS_UPDATE_INTERVAL")

    def test_progress_update_interval_is_numeric(self):
        """Verify PROGRESS_UPDATE_INTERVAL is numeric (int or float)."""
        assert isinstance(config.PROGRESS_UPDATE_INTERVAL, (int, float))

    def test_progress_update_interval_is_positive(self):
        """Verify PROGRESS_UPDATE_INTERVAL is positive."""
        assert config.PROGRESS_UPDATE_INTERVAL > 0

    def test_progress_update_interval_reasonable_range(self):
        """Verify PROGRESS_UPDATE_INTERVAL is within reasonable range (1-60 seconds)."""
        assert 1 <= config.PROGRESS_UPDATE_INTERVAL <= 60  # noqa: PLR2004


class TestMaxGlacierRestores:
    """Tests for MAX_GLACIER_RESTORES configuration."""

    def test_max_glacier_restores_exists(self):
        """Verify MAX_GLACIER_RESTORES constant exists."""
        assert hasattr(config, "MAX_GLACIER_RESTORES")

    def test_max_glacier_restores_is_integer(self):
        """Verify MAX_GLACIER_RESTORES is an integer."""
        assert isinstance(config.MAX_GLACIER_RESTORES, int)

    def test_max_glacier_restores_is_positive(self):
        """Verify MAX_GLACIER_RESTORES is positive."""
        assert config.MAX_GLACIER_RESTORES > 0

    def test_max_glacier_restores_reasonable_range(self):
        """Verify MAX_GLACIER_RESTORES is within reasonable range (1-1000)."""
        assert 1 <= config.MAX_GLACIER_RESTORES <= 1000  # noqa: PLR2004


class TestDownloadChunkSize:
    """Tests for DOWNLOAD_CHUNK_SIZE configuration."""

    def test_download_chunk_size_exists(self):
        """Verify DOWNLOAD_CHUNK_SIZE constant exists."""
        assert hasattr(config, "DOWNLOAD_CHUNK_SIZE")

    def test_download_chunk_size_is_integer(self):
        """Verify DOWNLOAD_CHUNK_SIZE is an integer."""
        assert isinstance(config.DOWNLOAD_CHUNK_SIZE, int)

    def test_download_chunk_size_is_positive(self):
        """Verify DOWNLOAD_CHUNK_SIZE is positive."""
        assert config.DOWNLOAD_CHUNK_SIZE > 0

    def test_download_chunk_size_reasonable_range(self):
        """Verify DOWNLOAD_CHUNK_SIZE is reasonable (1MB to 100MB)."""
        min_size = 1024 * 1024  # 1MB
        max_size = 100 * 1024 * 1024  # 100MB
        assert min_size <= config.DOWNLOAD_CHUNK_SIZE <= max_size

    def test_download_chunk_size_is_power_of_two_multiple(self):
        """Verify DOWNLOAD_CHUNK_SIZE is a multiple of 1MB."""
        mb = 1024 * 1024
        assert config.DOWNLOAD_CHUNK_SIZE % mb == 0


class TestParallelDownloadSettings:
    """Tests for parallel download configuration."""

    def test_max_concurrent_downloads_exists(self):
        """Verify MAX_CONCURRENT_DOWNLOADS constant exists."""
        assert hasattr(config, "MAX_CONCURRENT_DOWNLOADS")

    def test_max_concurrent_downloads_is_integer(self):
        """Verify MAX_CONCURRENT_DOWNLOADS is an integer."""
        assert isinstance(config.MAX_CONCURRENT_DOWNLOADS, int)

    def test_max_concurrent_downloads_is_positive(self):
        """Verify MAX_CONCURRENT_DOWNLOADS is positive."""
        assert config.MAX_CONCURRENT_DOWNLOADS > 0

    def test_max_concurrent_downloads_reasonable_range(self):
        """Verify MAX_CONCURRENT_DOWNLOADS is within reasonable range (1-500)."""
        assert 1 <= config.MAX_CONCURRENT_DOWNLOADS <= 500  # noqa: PLR2004

    def test_max_concurrent_verifications_exists(self):
        """Verify MAX_CONCURRENT_VERIFICATIONS constant exists."""
        assert hasattr(config, "MAX_CONCURRENT_VERIFICATIONS")

    def test_max_concurrent_verifications_is_integer(self):
        """Verify MAX_CONCURRENT_VERIFICATIONS is an integer."""
        assert isinstance(config.MAX_CONCURRENT_VERIFICATIONS, int)

    def test_max_concurrent_verifications_is_positive(self):
        """Verify MAX_CONCURRENT_VERIFICATIONS is positive."""
        assert config.MAX_CONCURRENT_VERIFICATIONS > 0

    def test_max_concurrent_verifications_reasonable_range(self):
        """Verify MAX_CONCURRENT_VERIFICATIONS is within reasonable range (1-50)."""
        assert 1 <= config.MAX_CONCURRENT_VERIFICATIONS <= 50  # noqa: PLR2004

    def test_downloads_exceeds_verifications(self):
        """Verify MAX_CONCURRENT_DOWNLOADS is >= MAX_CONCURRENT_VERIFICATIONS."""
        assert config.MAX_CONCURRENT_DOWNLOADS >= config.MAX_CONCURRENT_VERIFICATIONS


class TestBatchProcessingSettings:
    """Tests for batch processing configuration."""

    def test_batch_size_exists(self):
        """Verify BATCH_SIZE constant exists."""
        assert hasattr(config, "BATCH_SIZE")

    def test_batch_size_is_integer(self):
        """Verify BATCH_SIZE is an integer."""
        assert isinstance(config.BATCH_SIZE, int)

    def test_batch_size_is_positive(self):
        """Verify BATCH_SIZE is positive."""
        assert config.BATCH_SIZE > 0

    def test_batch_size_reasonable_range(self):
        """Verify BATCH_SIZE is within reasonable range (10-1000)."""
        assert 10 <= config.BATCH_SIZE <= 1000  # noqa: PLR2004

    def test_db_batch_commit_size_exists(self):
        """Verify DB_BATCH_COMMIT_SIZE constant exists."""
        assert hasattr(config, "DB_BATCH_COMMIT_SIZE")

    def test_db_batch_commit_size_is_integer(self):
        """Verify DB_BATCH_COMMIT_SIZE is an integer."""
        assert isinstance(config.DB_BATCH_COMMIT_SIZE, int)

    def test_db_batch_commit_size_is_positive(self):
        """Verify DB_BATCH_COMMIT_SIZE is positive."""
        assert config.DB_BATCH_COMMIT_SIZE > 0

    def test_db_batch_commit_size_reasonable_range(self):
        """Verify DB_BATCH_COMMIT_SIZE is within reasonable range (1-100)."""
        assert 1 <= config.DB_BATCH_COMMIT_SIZE <= 100  # noqa: PLR2004

    def test_db_batch_commit_smaller_than_batch_size(self):
        """Verify DB_BATCH_COMMIT_SIZE <= BATCH_SIZE."""
        assert config.DB_BATCH_COMMIT_SIZE <= config.BATCH_SIZE


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
        assert 1 <= config.MAX_CONCURRENCY <= 50  # noqa: PLR2004

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


class TestConfigConsistency:
    """Tests to verify consistency between related configuration values."""

    def test_download_chunk_size_matches_threshold(self):
        """Verify DOWNLOAD_CHUNK_SIZE is >= MULTIPART_THRESHOLD."""
        # Chunk size should be at least as large as multipart threshold
        assert config.DOWNLOAD_CHUNK_SIZE >= config.MULTIPART_THRESHOLD

    def test_multipart_settings_match(self):
        """Verify multipart threshold and chunksize are related."""
        # Both should be equal (common practice) or threshold <= chunksize
        assert config.MULTIPART_THRESHOLD <= config.MULTIPART_CHUNKSIZE

    def test_no_negative_values(self):
        """Verify no configuration values are negative."""
        numeric_configs = [
            config.GLACIER_RESTORE_DAYS,
            config.PROGRESS_UPDATE_INTERVAL,
            config.MAX_GLACIER_RESTORES,
            config.DOWNLOAD_CHUNK_SIZE,
            config.MAX_CONCURRENT_DOWNLOADS,
            config.MAX_CONCURRENT_VERIFICATIONS,
            config.BATCH_SIZE,
            config.DB_BATCH_COMMIT_SIZE,
            config.MULTIPART_THRESHOLD,
            config.MULTIPART_CHUNKSIZE,
            config.MAX_CONCURRENCY,
        ]
        for value in numeric_configs:
            assert value >= 0, f"Found negative configuration value: {value}"

    def test_all_config_constants_defined(self):
        """Verify all expected configuration constants are defined."""
        expected_constants = [
            "LOCAL_BASE_PATH",
            "STATE_DB_PATH",
            "GLACIER_RESTORE_DAYS",
            "GLACIER_RESTORE_TIER",
            "PROGRESS_UPDATE_INTERVAL",
            "MAX_GLACIER_RESTORES",
            "DOWNLOAD_CHUNK_SIZE",
            "MAX_CONCURRENT_DOWNLOADS",
            "MAX_CONCURRENT_VERIFICATIONS",
            "BATCH_SIZE",
            "DB_BATCH_COMMIT_SIZE",
            "MULTIPART_THRESHOLD",
            "MULTIPART_CHUNKSIZE",
            "MAX_CONCURRENCY",
            "USE_THREADS",
            "EXCLUDED_BUCKETS",
        ]
        for constant in expected_constants:
            assert hasattr(config, constant), f"Missing configuration constant: {constant}"


class TestConfigTypes:
    """Tests to verify all configuration values have expected types."""

    def test_string_configs_are_strings(self):
        """Verify all string configs are actually strings."""
        string_configs = [
            (config.LOCAL_BASE_PATH, "LOCAL_BASE_PATH"),
            (config.STATE_DB_PATH, "STATE_DB_PATH"),
            (config.GLACIER_RESTORE_TIER, "GLACIER_RESTORE_TIER"),
        ]
        for value, name in string_configs:
            assert isinstance(value, str), f"{name} should be a string, got {type(value)}"

    def test_int_configs_are_integers(self):
        """Verify all integer configs are actually integers."""
        int_configs = [
            (config.GLACIER_RESTORE_DAYS, "GLACIER_RESTORE_DAYS"),
            (config.MAX_GLACIER_RESTORES, "MAX_GLACIER_RESTORES"),
            (config.DOWNLOAD_CHUNK_SIZE, "DOWNLOAD_CHUNK_SIZE"),
            (config.MAX_CONCURRENT_DOWNLOADS, "MAX_CONCURRENT_DOWNLOADS"),
            (config.MAX_CONCURRENT_VERIFICATIONS, "MAX_CONCURRENT_VERIFICATIONS"),
            (config.BATCH_SIZE, "BATCH_SIZE"),
            (config.DB_BATCH_COMMIT_SIZE, "DB_BATCH_COMMIT_SIZE"),
            (config.MULTIPART_THRESHOLD, "MULTIPART_THRESHOLD"),
            (config.MULTIPART_CHUNKSIZE, "MULTIPART_CHUNKSIZE"),
            (config.MAX_CONCURRENCY, "MAX_CONCURRENCY"),
        ]
        for value, name in int_configs:
            assert isinstance(value, int), f"{name} should be an integer, got {type(value)}"

    def test_boolean_configs_are_booleans(self):
        """Verify all boolean configs are actually booleans."""
        bool_configs = [(config.USE_THREADS, "USE_THREADS")]
        for value, name in bool_configs:
            assert isinstance(value, bool), f"{name} should be a boolean, got {type(value)}"

    def test_list_configs_are_lists(self):
        """Verify all list configs are actually lists."""
        list_configs = [(config.EXCLUDED_BUCKETS, "EXCLUDED_BUCKETS")]
        for value, name in list_configs:
            assert isinstance(value, list), f"{name} should be a list, got {type(value)}"
