"""Test suite package marker."""

import pytest

# Ensure helper modules used as pytest plugins are assertion-rewritten before import.
pytest.register_assert_rewrite("tests.explore_aurora_data_fixtures")
pytest.register_assert_rewrite("tests.unused_module_guard_test_utils")
