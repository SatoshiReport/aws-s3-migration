"""Shared constants used by AWS toolkit tests to keep expectations stable."""

DEFAULT_TEST_REGIONS = ["eu-west-2", "us-east-2", "us-west-2"]


def format_static_regions():
    """Return comma-separated string suitable for env overrides."""
    return ",".join(DEFAULT_TEST_REGIONS)
