"""Extra coverage for ``format_utils.parse_aws_cli_size`` edge cases."""

from __future__ import annotations

import pytest

from cost_toolkit.common.format_utils import parse_aws_cli_size


def test_parse_aws_cli_size_with_space():
    """Ensure strings like '1.5 GiB' parse correctly."""
    result = parse_aws_cli_size("1.5 GiB")
    assert result == 1_610_612_736


def test_parse_aws_cli_size_compact_suffix():
    """Handle inputs such as '512MiB' without a space."""
    result = parse_aws_cli_size("512MiB")
    assert result == 536_870_912


def test_parse_aws_cli_size_bytes_default():
    """Treat plain numbers as bytes."""
    assert parse_aws_cli_size("12345") == 12_345


def test_parse_aws_cli_size_invalid_string():
    """Invalid strings raise ValueError."""
    with pytest.raises(ValueError):
        parse_aws_cli_size("not-a-size")
