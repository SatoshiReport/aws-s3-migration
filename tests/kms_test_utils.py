"""Shared helpers for KMS audit tests."""

from __future__ import annotations

from unittest.mock import MagicMock


def build_kms_key_metadata(manager="CUSTOMER"):
    """Return a basic KeyMetadata dictionary."""
    return {
        "KeyManager": manager,
        "Description": "Test",
        "KeyState": "Enabled",
        "CreationDate": "2024-01-01",
    }


def build_kms_client(manager="CUSTOMER"):
    """Create a mock KMS client with describe/list responses."""
    mock_kms = MagicMock()
    mock_kms.describe_key.return_value = {"KeyMetadata": build_kms_key_metadata(manager)}
    mock_kms.list_aliases.return_value = {"Aliases": []}
    mock_kms.list_grants.return_value = {"Grants": []}
    return mock_kms
