"""Comprehensive tests for aws_rds_network_interface_audit.py - Part 4."""

from __future__ import annotations

from unittest.mock import patch

from botocore.exceptions import ClientError

from cost_toolkit.scripts.audit.aws_rds_network_interface_audit import (
    _print_cleanup_recommendations,
    _print_network_interfaces,
    _print_rds_cluster,
    _print_rds_details,
    _print_rds_instance,
    _print_region_scan_results,
    main,
)


def test_print_region_scan_results_print_results(capsys):
    """Test printing region scan results."""
    rds_data = {
        "total_instances": 2,
        "total_clusters": 1,
    }
    rds_interfaces = [{"NetworkInterfaceId": "eni-123"}]

    _print_region_scan_results(rds_data, rds_interfaces)

    captured = capsys.readouterr()
    assert "RDS Instances: 2" in captured.out
    assert "RDS Clusters: 1" in captured.out
    assert "RDS Network Interfaces: 1" in captured.out


def test_print_region_scan_results_no_resources_no_resources(capsys):
    """Test printing when no resources found."""
    _print_region_scan_results(None, [])

    captured = capsys.readouterr()
    assert "No RDS resources found" in captured.out


def test_print_rds_instance(capsys):
    """Test printing RDS instance details."""
    instance = {
        "identifier": "mydb",
        "engine": "postgres",
        "engine_version": "14.7",
        "instance_class": "db.t3.micro",
        "status": "available",
        "vpc_id": "vpc-123",
        "endpoint": "mydb.us-east-1.rds.amazonaws.com",
        "port": 5432,
        "publicly_accessible": False,
        "storage_type": "gp3",
        "allocated_storage": 100,
        "creation_time": "2024-01-01T00:00:00Z",
    }

    _print_rds_instance(instance)

    captured = capsys.readouterr()
    assert "mydb" in captured.out
    assert "Engine: postgres 14.7" in captured.out
    assert "Class: db.t3.micro" in captured.out
    assert "Status: available" in captured.out
    assert "VPC: vpc-123" in captured.out
    assert "Endpoint: mydb.us-east-1.rds.amazonaws.com:5432" in captured.out
    assert "Public: False" in captured.out
    assert "Storage: gp3 (100 GB)" in captured.out


class TestPrintRdsCluster:
    """Tests for _print_rds_cluster function."""

    def test_print_rds_cluster_provisioned(self, capsys):
        """Test printing provisioned RDS cluster details."""
        cluster = {
            "identifier": "aurora-cluster",
            "engine": "aurora-postgresql",
            "engine_version": "14.6",
            "engine_mode": "provisioned",
            "status": "available",
            "vpc_id": "vpc-456",
            "endpoint": "aurora.cluster-xyz.us-east-1.rds.amazonaws.com",
            "reader_endpoint": "aurora.cluster-ro-xyz.us-east-1.rds.amazonaws.com",
            "port": 5432,
            "serverless_v2_scaling": {},
            "creation_time": "2024-01-01T00:00:00Z",
        }

        _print_rds_cluster(cluster)

        captured = capsys.readouterr()
        assert "aurora-cluster" in captured.out
        assert "Engine: aurora-postgresql 14.6" in captured.out
        assert "Mode: provisioned" in captured.out
        assert "Status: available" in captured.out
        assert "VPC: vpc-456" in captured.out
        assert "Endpoint: aurora.cluster-xyz.us-east-1.rds.amazonaws.com:5432" in captured.out
        assert "Reader: aurora.cluster-ro-xyz.us-east-1.rds.amazonaws.com" in captured.out

    def test_print_rds_cluster_serverless_v2(self, capsys):
        """Test printing serverless v2 cluster details."""
        cluster = {
            "identifier": "serverless-cluster",
            "engine": "aurora-mysql",
            "engine_version": "5.7",
            "engine_mode": "provisioned",
            "status": "available",
            "vpc_id": "vpc-789",
            "endpoint": "serverless.cluster-abc.us-west-2.rds.amazonaws.com",
            "reader_endpoint": "N/A",
            "port": 3306,
            "serverless_v2_scaling": {"MinCapacity": 0.5, "MaxCapacity": 2.0},
            "creation_time": "2024-02-01T00:00:00Z",
        }

        _print_rds_cluster(cluster)

        captured = capsys.readouterr()
        assert "serverless-cluster" in captured.out
        assert "Serverless V2:" in captured.out
        assert "MinCapacity" in captured.out


def test_print_rds_details_print_details(capsys):
    """Test printing RDS details."""
    regions_data = [
        {
            "region": "us-east-1",
            "instances": [
                {
                    "identifier": "db-1",
                    "engine": "postgres",
                    "engine_version": "14.7",
                    "instance_class": "db.t3.micro",
                    "status": "available",
                    "vpc_id": "vpc-123",
                    "endpoint": "db-1.us-east-1.rds.amazonaws.com",
                    "port": 5432,
                    "publicly_accessible": False,
                    "storage_type": "gp3",
                    "allocated_storage": 100,
                    "creation_time": "2024-01-01T00:00:00Z",
                }
            ],
            "clusters": [],
        }
    ]

    _print_rds_details(regions_data)

    captured = capsys.readouterr()
    assert "RDS INSTANCES AND CLUSTERS DETAILS" in captured.out
    assert "Region: us-east-1" in captured.out
    assert "RDS Instances:" in captured.out


def test_print_network_interfaces_print_interfaces(capsys):
    """Test printing network interfaces."""
    interfaces = [
        {
            "interface_id": "eni-123",
            "region": "us-east-1",
            "vpc_id": "vpc-123",
            "subnet_id": "subnet-123",
            "private_ip": "10.0.1.10",
            "public_ip": "1.2.3.4",
            "status": "in-use",
        }
    ]

    _print_network_interfaces(interfaces)

    captured = capsys.readouterr()
    assert "RDS NETWORK INTERFACES DETAILS" in captured.out
    assert "Interface: eni-123 (us-east-1)" in captured.out
    assert "VPC: vpc-123" in captured.out
    assert "Private IP: 10.0.1.10" in captured.out
    assert "Public IP: 1.2.3.4" in captured.out


class TestPrintCleanupRecommendations:
    """Tests for _print_cleanup_recommendations function."""

    def test_print_orphaned_interfaces(self, capsys):
        """Test recommendations for orphaned interfaces."""
        _print_cleanup_recommendations(5, 0, 0)

        captured = capsys.readouterr()
        assert "CLEANUP ANALYSIS AND RECOMMENDATIONS" in captured.out
        assert "ORPHANED RDS NETWORK INTERFACES DETECTED" in captured.out
        assert "Found RDS network interfaces but no active RDS instances/clusters" in captured.out

    def test_print_excess_interfaces(self, capsys):
        """Test recommendations for excess interfaces."""
        _print_cleanup_recommendations(10, 2, 1)

        captured = capsys.readouterr()
        assert "EXCESS RDS NETWORK INTERFACES DETECTED" in captured.out
        assert "Found 10 RDS interfaces but only 3 RDS resources" in captured.out

    def test_print_mixed_deployment(self, capsys):
        """Test recommendations for mixed deployment."""
        _print_cleanup_recommendations(5, 2, 3)

        captured = capsys.readouterr()
        assert "MIXED RDS DEPLOYMENT DETECTED" in captured.out
        assert "Both traditional instances and serverless clusters found" in captured.out

    def test_print_serverless_only(self, capsys):
        """Test recommendations for serverless only."""
        _print_cleanup_recommendations(3, 0, 3)

        captured = capsys.readouterr()
        assert "SERVERLESS RDS DEPLOYMENT" in captured.out
        assert "Only serverless clusters found - optimal for cost" in captured.out

    def test_print_clean_configuration(self, capsys):
        """Test recommendations for clean configuration."""
        _print_cleanup_recommendations(2, 2, 0)

        captured = capsys.readouterr()
        assert "CLEAN RDS CONFIGURATION" in captured.out
        assert "RDS network interfaces match RDS resources" in captured.out


def test_main_function_main_execution(capsys):
    """Test main function execution."""
    with patch(
        "cost_toolkit.scripts.audit.aws_rds_network_interface_audit.load_aws_credentials"
    ) as mock_creds:
        with patch(
            "cost_toolkit.scripts.audit.aws_rds_network_interface_audit.get_all_regions"
        ) as mock_regions:
            with patch(
                "cost_toolkit.scripts.audit.aws_rds_network_interface_audit._scan_region_resources"
            ) as mock_scan:
                mock_creds.return_value = ("test-key", "test-secret")
                mock_regions.return_value = ["us-east-1"]
                mock_scan.return_value = (
                    {
                        "region": "us-east-1",
                        "instances": [],
                        "clusters": [],
                        "total_instances": 0,
                        "total_clusters": 0,
                    },
                    [],
                    [],
                )

                main()

    captured = capsys.readouterr()
    assert "AWS RDS and Network Interface Correlation Audit" in captured.out
    assert "RDS AND NETWORK INTERFACE AUDIT SUMMARY" in captured.out
    assert "CLEANUP ANALYSIS AND RECOMMENDATIONS" in captured.out


def test_main_client_error_main_error(capsys):
    """Test main function with client error."""
    with patch(
        "cost_toolkit.scripts.audit.aws_rds_network_interface_audit.load_aws_credentials"
    ) as mock_creds:
        with patch(
            "cost_toolkit.scripts.audit.aws_rds_network_interface_audit.get_all_regions"
        ) as mock_regions:
            mock_creds.return_value = ("test-key", "test-secret")
            mock_regions.side_effect = ClientError(
                {"Error": {"Code": "AccessDenied"}}, "describe_regions"
            )

            try:
                main()
            except ClientError:
                pass

    captured = capsys.readouterr()
    assert "Critical error during RDS audit" in captured.out
