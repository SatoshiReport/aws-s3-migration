"""Shared helpers for Lightsail cleanup tests."""

from __future__ import annotations

from unittest.mock import MagicMock

STANDARD_LIGHTSAIL_RESOURCES = (
    {"name": "inst1", "state": {"name": "running"}, "bundleId": "nano_2_0"},
    {"name": "db1", "state": "available", "relationalDatabaseBundleId": "micro_1_0"},
)


def build_lightsail_client(instances=None, databases=None):
    """Return a MagicMock Lightsail client with preset instances/databases."""
    mock_ls = MagicMock()
    default_instances = [STANDARD_LIGHTSAIL_RESOURCES[0]]
    default_databases = [STANDARD_LIGHTSAIL_RESOURCES[1]]
    instance_payload = default_instances if instances is None else instances
    database_payload = default_databases if databases is None else databases
    mock_ls.get_instances.return_value = {"instances": list(instance_payload)}
    mock_ls.get_relational_databases.return_value = {"relationalDatabases": list(database_payload)}
    return mock_ls


def build_empty_lightsail_client():
    """Return a Lightsail client mock with no instances or databases."""
    return build_lightsail_client(instances=[], databases=[])
