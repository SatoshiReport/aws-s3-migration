"""
Unit tests for config.py Glacier and progress-related configurations.

Tests verify:
- Glacier restore settings (days, tier)
- Progress update interval
- Maximum Glacier restores
"""

import config


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
