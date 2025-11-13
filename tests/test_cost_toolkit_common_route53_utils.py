"""Tests for cost_toolkit/common/route53_utils.py module."""

from __future__ import annotations

from cost_toolkit.common.route53_utils import parse_hosted_zone


def test_parse_hosted_zone_basic():
    """Test parse_hosted_zone with basic zone information."""
    zone = {
        "Id": "/hostedzone/Z1234567890ABC",
        "Name": "example.com.",
        "ResourceRecordSetCount": 10,
    }

    result = parse_hosted_zone(zone)

    assert result["zone_id"] == "Z1234567890ABC"
    assert result["zone_name"] == "example.com."
    assert result["is_private"] is False
    assert result["record_count"] == 10


def test_parse_hosted_zone_private():
    """Test parse_hosted_zone with private hosted zone."""
    zone = {
        "Id": "/hostedzone/Z9876543210XYZ",
        "Name": "internal.example.com.",
        "Config": {
            "PrivateZone": True,
        },
        "ResourceRecordSetCount": 5,
    }

    result = parse_hosted_zone(zone)

    assert result["zone_id"] == "Z9876543210XYZ"
    assert result["zone_name"] == "internal.example.com."
    assert result["is_private"] is True
    assert result["record_count"] == 5


def test_parse_hosted_zone_no_config():
    """Test parse_hosted_zone when Config is missing."""
    zone = {
        "Id": "/hostedzone/Z1111111111AAA",
        "Name": "test.com.",
        "ResourceRecordSetCount": 2,
    }

    result = parse_hosted_zone(zone)

    assert result["zone_id"] == "Z1111111111AAA"
    assert result["zone_name"] == "test.com."
    assert result["is_private"] is False
    assert result["record_count"] == 2


def test_parse_hosted_zone_zero_records():
    """Test parse_hosted_zone with zero records."""
    zone = {
        "Id": "/hostedzone/Z0000000000ZZZ",
        "Name": "empty.com.",
    }

    result = parse_hosted_zone(zone)

    assert result["zone_id"] == "Z0000000000ZZZ"
    assert result["zone_name"] == "empty.com."
    assert result["is_private"] is False
    assert result["record_count"] == 0


def test_parse_hosted_zone_id_without_prefix():
    """Test parse_hosted_zone handles IDs without /hostedzone/ prefix."""
    zone = {
        "Id": "Z5555555555BBB",
        "Name": "simple.com.",
        "ResourceRecordSetCount": 15,
    }

    result = parse_hosted_zone(zone)

    # The split("/")[-1] should still work
    assert result["zone_id"] == "Z5555555555BBB"
    assert result["zone_name"] == "simple.com."


def test_parse_hosted_zone_all_fields():
    """Test parse_hosted_zone returns all expected fields."""
    zone = {
        "Id": "/hostedzone/ZFULL",
        "Name": "full.example.com.",
        "Config": {"PrivateZone": False},
        "ResourceRecordSetCount": 25,
    }

    result = parse_hosted_zone(zone)

    assert "zone_id" in result
    assert "zone_name" in result
    assert "is_private" in result
    assert "record_count" in result
    assert len(result) == 4
