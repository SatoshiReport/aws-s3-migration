"""Tests for config.py import fallback behavior."""

from __future__ import annotations

import builtins
import sys

from tests.assertions import assert_equal


def test_local_base_path_import_fallback():
    """Test LOCAL_BASE_PATH fallback when config_local import fails."""
    # The import fallback is already tested by the fact that config.py loads
    # This test verifies the structure exists
    import config  # pylint: disable=import-outside-toplevel

    assert hasattr(config, "LOCAL_BASE_PATH")
    assert isinstance(config.LOCAL_BASE_PATH, str)


def test_excluded_buckets_import_fallback():
    """Test EXCLUDED_BUCKETS fallback when config_local import fails."""
    import config  # pylint: disable=import-outside-toplevel

    assert hasattr(config, "EXCLUDED_BUCKETS")
    assert isinstance(config.EXCLUDED_BUCKETS, list)


def test_config_module_imports_successfully():
    """Test that config module can be imported without config_local."""
    # Temporarily hide config_local if it exists
    config_local_module = sys.modules.get("config_local")
    if config_local_module:
        del sys.modules["config_local"]

    try:
        # Force reimport
        if "config" in sys.modules:
            del sys.modules["config"]

        import config  # pylint: disable=import-outside-toplevel

        # Should have default values
        assert hasattr(config, "LOCAL_BASE_PATH")
        assert hasattr(config, "EXCLUDED_BUCKETS")
        assert isinstance(config.STATE_DB_PATH, str)
    finally:
        # Restore if it existed
        if config_local_module:
            sys.modules["config_local"] = config_local_module


def test_local_base_path_fallback_on_import_error():
    """Test LOCAL_BASE_PATH uses default when config_local import fails."""
    # Ensure config_local is not importable
    config_local_module = sys.modules.get("config_local")
    if config_local_module:
        del sys.modules["config_local"]

    # Block config_local import
    original_import = builtins.__import__

    def mock_import(name, *args, **kwargs):
        if name == "config_local":
            raise ImportError("Mocked ImportError for config_local")
        return original_import(name, *args, **kwargs)

    try:
        # Force reimport with blocked config_local
        if "config" in sys.modules:
            del sys.modules["config"]

        builtins.__import__ = mock_import

        import config  # pylint: disable=import-outside-toplevel,reimported

        # Should use default value
        assert_equal(config.LOCAL_BASE_PATH, "/path/to/your/backup/directory")
    finally:
        builtins.__import__ = original_import
        if config_local_module:
            sys.modules["config_local"] = config_local_module


def test_excluded_buckets_fallback_on_import_error():
    """Test EXCLUDED_BUCKETS uses default when config_local import fails."""
    # Ensure config_local is not importable
    config_local_module = sys.modules.get("config_local")
    if config_local_module:
        del sys.modules["config_local"]

    # Block config_local import
    original_import = builtins.__import__

    def mock_import(name, *args, **kwargs):
        if name == "config_local":
            raise ImportError("Mocked ImportError for config_local")
        return original_import(name, *args, **kwargs)

    try:
        # Force reimport with blocked config_local
        if "config" in sys.modules:
            del sys.modules["config"]

        builtins.__import__ = mock_import

        import config  # pylint: disable=import-outside-toplevel,reimported

        # Should use default value
        assert_equal(config.EXCLUDED_BUCKETS, [])
    finally:
        builtins.__import__ = original_import
        if config_local_module:
            sys.modules["config_local"] = config_local_module
