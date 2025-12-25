"""Shared helpers for AWS region-related tests."""

from __future__ import annotations

from typing import Sequence
from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError

REGION_LIST: Sequence[dict] = (
    {"RegionName": "us-east-1"},
    {"RegionName": "us-west-2"},
    {"RegionName": "eu-west-1"},
)


def mock_region_client_success(mock_create_client):
    """Configure the EC2 client mock to return a standard region list."""
    mock_ec2 = MagicMock()
    mock_create_client.return_value = mock_ec2
    mock_ec2.describe_regions.return_value = {"Regions": list(REGION_LIST)}
    return mock_ec2


def mock_region_client_error(mock_create_client, code: str = "AccessDenied"):
    """Configure the EC2 client mock to raise a ClientError for describe_regions."""
    mock_ec2 = MagicMock()
    mock_ec2.describe_regions.side_effect = ClientError({"Error": {"Code": code}}, "describe_regions")
    mock_create_client.return_value = mock_ec2
    return mock_ec2


ELASTIC_IP_RESPONSE = {
    "Addresses": [
        {
            "PublicIp": "54.123.45.67",
            "AllocationId": "eipalloc-123",
            "AssociationId": "eipassoc-456",
            "InstanceId": "i-123",
            "Domain": "vpc",
            "Tags": [],
        },
        {
            "PublicIp": "54.123.45.68",
            "AllocationId": "eipalloc-456",
            "Domain": "vpc",
            "Tags": [],
        },
    ]
}

SINGLE_ELASTIC_IP_RESPONSE = {
    "Addresses": [
        {
            "PublicIp": "54.123.45.67",
            "AllocationId": "eipalloc-123",
        }
    ]
}


def assert_regions_success(get_all_regions_func, mock_create_client, monkeypatch):
    """Run standard success assertions for get_all_regions implementations."""
    monkeypatch.delenv("COST_TOOLKIT_STATIC_AWS_REGIONS", raising=False)
    mock_region_client_success(mock_create_client)
    regions = get_all_regions_func()
    assert len(regions) == 3
    assert "us-east-1" in regions
    assert "us-west-2" in regions
    assert "eu-west-1" in regions
    return regions


def assert_regions_error(get_all_regions_func, mock_create_client, monkeypatch):
    """Run standard error assertions for get_all_regions implementations."""
    monkeypatch.delenv("COST_TOOLKIT_STATIC_AWS_REGIONS", raising=False)
    mock_region_client_error(mock_create_client)
    with pytest.raises(ClientError):
        get_all_regions_func()
