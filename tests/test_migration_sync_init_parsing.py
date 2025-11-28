"""Comprehensive tests for migration_sync.py - Initialization."""

from unittest import mock

from migration_sync import BucketSyncer


class TestBucketSyncerInit:
    """Test BucketSyncer initialization"""

    def test_init_creates_syncer_with_attributes(self, tmp_path):
        """Test that BucketSyncer initializes with correct attributes"""
        fake_s3 = mock.Mock()
        fake_state = mock.Mock()
        base_path = tmp_path / "sync"

        syncer = BucketSyncer(fake_s3, fake_state, base_path)

        assert syncer.s3 is fake_s3
        assert syncer.state is fake_state
        assert syncer.base_path == base_path
        assert syncer.interrupted is False

    def test_interrupted_flag_defaults_to_false(self, tmp_path):
        """Test that interrupted flag is initialized to False"""
        fake_s3 = mock.Mock()
        fake_state = mock.Mock()
        syncer = BucketSyncer(fake_s3, fake_state, tmp_path)

        assert syncer.interrupted is False
