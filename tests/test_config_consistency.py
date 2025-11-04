"""
Unit tests for config.py consistency and type validation.

Tests verify:
- Consistency between related configuration values
- All expected constants are defined
- All configuration values have correct types
- No negative values where inappropriate
"""

import config


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
