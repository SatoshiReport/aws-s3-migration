"""Shared helpers for RDS audit tests."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import patch

import boto3

from cost_toolkit.scripts.audit import aws_rds_audit

DB_INSTANCE_SUMMARY = {
    "Engine": "postgres",
    "EngineVersion": "14.5",
    "DBInstanceClass": "db.t3.micro",
    "DBInstanceStatus": "available",
    "AllocatedStorage": 20,
    "StorageType": "gp3",
    "MultiAZ": False,
    "PubliclyAccessible": False,
    "InstanceCreateTime": datetime(2024, 1, 15, 10, 30),
}

AURORA_POSTGRES_CLUSTER = {
    "DBClusterIdentifier": "test-cluster",
    "Engine": "aurora-postgresql",
    "EngineVersion": "14.6",
    "Status": "available",
    "DatabaseName": "mydb",
    "MasterUsername": "admin",
    "MultiAZ": True,
    "StorageEncrypted": True,
    "ClusterCreateTime": datetime(2024, 1, 15, 10, 30),
}

AURORA_MYSQL_CLUSTER = {
    "DBClusterIdentifier": "aurora-cluster",
    "Engine": "aurora-mysql",
    "EngineVersion": "8.0",
    "Status": "available",
    "DatabaseName": "prod",
    "MasterUsername": "dbadmin",
    "MultiAZ": False,
    "StorageEncrypted": True,
    "ClusterCreateTime": datetime(2024, 1, 15, 10, 30),
}

SERVERLESS_V1_CLUSTER = {
    "DBClusterIdentifier": "serverless-cluster",
    "Engine": "aurora-mysql",
    "EngineVersion": "5.7",
    "Status": "available",
    "DatabaseName": "testdb",
    "MasterUsername": "admin",
    "MultiAZ": False,
    "StorageEncrypted": True,
    "ClusterCreateTime": datetime(2024, 1, 15, 10, 30),
    "EngineMode": "serverless",
    "ScalingConfigurationInfo": {"MinCapacity": 2, "MaxCapacity": 16},
}

SERVERLESS_V2_CLUSTER = {
    "DBClusterIdentifier": "serverless-v2",
    "Engine": "aurora-postgresql",
    "EngineVersion": "14.6",
    "Status": "available",
    "DatabaseName": "mydb",
    "MasterUsername": "postgres",
    "MultiAZ": True,
    "StorageEncrypted": True,
    "ClusterCreateTime": datetime(2024, 1, 15, 10, 30),
    "ServerlessV2ScalingConfiguration": {"MinCapacity": 0.5, "MaxCapacity": 4.0},
}


def run_audit_with_mock_clients(mock_ec2, create_rds_client):
    """Run audit_rds_databases with a boto3 client side effect wiring EC2 and RDS."""
    with patch.object(boto3, "client") as mock_client:

        def client_side_effect(service, **kwargs):
            if service == "ec2":
                return mock_ec2
            return create_rds_client(kwargs.get("region_name"))

        mock_client.side_effect = client_side_effect
        aws_rds_audit.audit_rds_databases()
