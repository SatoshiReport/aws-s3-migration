"""Comprehensive tests for aws_security_group_dependencies.py - Part 3: Main Functions."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from cost_toolkit.scripts.audit.aws_security_group_dependencies import (
    _print_dependency_details,
    _print_instances,
    _print_network_interfaces,
    _print_rds_instances,
    _print_security_group_rules,
    audit_security_group_dependencies,
    check_security_group_dependencies,
    main,
)


class TestCheckSecurityGroupDependencies:
    """Tests for check_security_group_dependencies function."""

    def test_check_dependencies_success(self):
        """Test successful dependency check."""
        with (
            patch(
                "cost_toolkit.scripts.audit.aws_security_group_dependencies._collect_network_interface_deps"  # pylint: disable=line-too-long
            ) as mock_eni,
            patch(
                "cost_toolkit.scripts.audit.aws_security_group_dependencies._collect_instance_deps"
            ) as mock_instances,
            patch(
                "cost_toolkit.scripts.audit.aws_security_group_dependencies._collect_sg_rule_refs"
            ) as mock_sg_rules,
            patch(
                "cost_toolkit.scripts.audit.aws_security_group_dependencies._collect_rds_deps"
            ) as mock_rds,
        ):
            mock_ec2_client = MagicMock()
            mock_eni.return_value = [{"interface_id": "eni-123"}]
            mock_instances.return_value = [{"instance_id": "i-123"}]
            mock_sg_rules.return_value = [{"referencing_sg": "sg-other"}]
            mock_rds.return_value = [{"db_instance_id": "db-123"}]

            result = check_security_group_dependencies(
                mock_ec2_client, "sg-test", "us-east-1", "key", "secret"
            )

            assert len(result["network_interfaces"]) == 1
            assert len(result["instances"]) == 1
            assert len(result["security_group_rules"]) == 1
            assert len(result["rds_instances"]) == 1

    def test_check_dependencies_client_error(self, capsys):
        """Test dependency check with ClientError."""
        with patch(
            "cost_toolkit.scripts.audit.aws_security_group_dependencies._collect_network_interface_deps"  # pylint: disable=line-too-long
        ) as mock_eni:
            mock_ec2_client = MagicMock()
            mock_eni.side_effect = ClientError(
                {"Error": {"Code": "AccessDenied"}}, "describe_network_interfaces"
            )

            result = check_security_group_dependencies(
                mock_ec2_client, "sg-test", "us-east-1", "key", "secret"
            )

            assert not result["network_interfaces"]
            captured = capsys.readouterr()
            assert "Error checking dependencies" in captured.out


class TestPrintBasicFunctions:
    """Tests for basic print helper functions."""

    def test_print_network_interfaces(self, capsys):
        """Test printing network interfaces."""
        enis = [
            {
                "interface_id": "eni-123",
                "status": "in-use",
                "description": "Primary",
                "attachment": {"InstanceId": "i-123"},
            },
            {
                "interface_id": "eni-456",
                "status": "available",
                "description": "Secondary",
                "attachment": {},
            },
        ]

        _print_network_interfaces(enis)

        captured = capsys.readouterr()
        assert "Network Interfaces (2)" in captured.out
        assert "eni-123" in captured.out
        assert "Attached to i-123" in captured.out
        assert "eni-456" in captured.out
        assert "Unattached" in captured.out

    def test_print_instances(self, capsys):
        """Test printing EC2 instances."""
        instances = [
            {"instance_id": "i-123", "name": "web-server", "state": "running"},
            {"instance_id": "i-456", "name": "db-server", "state": "stopped"},
        ]

        _print_instances(instances)

        captured = capsys.readouterr()
        assert "Instances (2)" in captured.out
        assert "i-123" in captured.out
        assert "web-server" in captured.out
        assert "running" in captured.out

    def test_print_rds_instances(self, capsys):
        """Test printing RDS instances."""
        rds_instances = [
            {
                "db_instance_id": "db-123",
                "engine": "postgres",
                "db_instance_status": "available",
            }
        ]

        _print_rds_instances(rds_instances)

        captured = capsys.readouterr()
        assert "RDS Instances (1)" in captured.out
        assert "db-123" in captured.out
        assert "postgres" in captured.out

    def test_print_security_group_rules(self, capsys):
        """Test printing security group rules."""
        rules = [
            {
                "referencing_sg": "sg-123",
                "referencing_sg_name": "web-sg",
                "rule_type": "inbound",
                "protocol": "tcp",
                "port_range": "80-80",
            }
        ]

        _print_security_group_rules(rules)

        captured = capsys.readouterr()
        assert "Referenced by Security Group Rules (1)" in captured.out
        assert "sg-123" in captured.out
        assert "web-sg" in captured.out
        assert "inbound" in captured.out


class TestPrintDependencyDetails:
    """Tests for _print_dependency_details function."""

    def test_print_dependency_details_with_dependencies(self):
        """Test printing dependency details with dependencies."""
        dependencies = {
            "network_interfaces": [
                {
                    "interface_id": "eni-123",
                    "status": "in-use",
                    "description": "Primary",
                    "attachment": {"InstanceId": "i-123"},
                }
            ],
            "instances": [{"instance_id": "i-123", "name": "test", "state": "running"}],
            "rds_instances": [],
            "security_group_rules": [],
        }

        # Mock the print functions to avoid full output
        with (
            patch(
                "cost_toolkit.scripts.audit.aws_security_group_dependencies._print_network_interfaces"  # pylint: disable=line-too-long
            ),
            patch("cost_toolkit.scripts.audit.aws_security_group_dependencies._print_instances"),
        ):
            _print_dependency_details(dependencies)

    def test_print_dependency_details_with_rds_and_rules(self):
        """Test printing dependency details with RDS and security group rules."""
        dependencies = {
            "network_interfaces": [],
            "instances": [],
            "rds_instances": [{"db_instance_id": "db-123"}],
            "security_group_rules": [{"referencing_sg": "sg-123"}],
        }

        with (
            patch(
                "cost_toolkit.scripts.audit.aws_security_group_dependencies._print_rds_instances"  # pylint: disable=line-too-long
            ),
            patch(
                "cost_toolkit.scripts.audit.aws_security_group_dependencies._print_security_group_rules"  # pylint: disable=line-too-long
            ),
        ):
            _print_dependency_details(dependencies)

    def test_print_dependency_details_no_dependencies(self, capsys):
        """Test printing dependency details with no dependencies."""
        dependencies = {
            "network_interfaces": [],
            "instances": [],
            "rds_instances": [],
            "security_group_rules": [],
        }  # pylint: disable=line-too-long

        _print_dependency_details(dependencies)
        # pylint: disable=line-too-long
        captured = capsys.readouterr()
        assert "No obvious dependencies found" in captured.out


class TestAuditSecurityGroupDependencies:
    """Tests for audit_security_group_dependencies function."""

    def test_audit_success(self, capsys):
        """Test successful audit."""
        with (
            patch("cost_toolkit.common.credential_utils.setup_aws_credentials") as mock_creds,
            patch("boto3.client") as mock_boto_client,
            patch(
                "cost_toolkit.scripts.audit.aws_security_group_dependencies.check_security_group_dependencies"  # pylint: disable=line-too-long
            ) as mock_check,
            patch(
                "cost_toolkit.scripts.audit.aws_security_group_dependencies._print_dependency_details"  # pylint: disable=line-too-long
            ),
        ):
            mock_creds.return_value = ("key", "secret")
            mock_boto_client.return_value = MagicMock()
            mock_check.return_value = {
                "network_interfaces": [],  # pylint: disable=line-too-long
                "instances": [],
                "rds_instances": [],
                "security_group_rules": [],
            }

            audit_security_group_dependencies()

            captured = capsys.readouterr()  # pylint: disable=line-too-long
            assert "AWS Security Group Dependencies Audit" in captured.out
            assert "CLEANUP RECOMMENDATIONS" in captured.out

    def test_audit_with_dependencies(self, capsys):
        """Test audit with found dependencies."""
        with (
            patch("cost_toolkit.common.credential_utils.setup_aws_credentials") as mock_creds,
            patch("boto3.client") as mock_boto_client,
            patch(
                "cost_toolkit.scripts.audit.aws_security_group_dependencies.check_security_group_dependencies"  # pylint: disable=line-too-long
            ) as mock_check,
            patch(
                "cost_toolkit.scripts.audit.aws_security_group_dependencies._print_dependency_details"  # pylint: disable=line-too-long
            ),
        ):
            mock_creds.return_value = ("key", "secret")
            mock_boto_client.return_value = MagicMock()
            mock_check.return_value = {
                "network_interfaces": [{"interface_id": "eni-123"}],
                "instances": [{"instance_id": "i-123"}],
                "rds_instances": [],
                "security_group_rules": [],
            }

            audit_security_group_dependencies()

            captured = capsys.readouterr()
            assert "AWS Security Group Dependencies Audit" in captured.out


class TestMain:
    """Tests for main function."""

    def test_main_success(self):
        """Test successful main execution."""
        with patch(
            "cost_toolkit.scripts.audit.aws_security_group_dependencies.audit_security_group_dependencies"  # pylint: disable=line-too-long
        ):
            main()

    def test_main_client_error(self):
        """Test main with ClientError."""
        with (
            patch(
                "cost_toolkit.scripts.audit.aws_security_group_dependencies.audit_security_group_dependencies"  # pylint: disable=line-too-long
            ) as mock_audit,
            pytest.raises(SystemExit) as exc_info,
        ):
            mock_audit.side_effect = ClientError(
                {"Error": {"Code": "AccessDenied"}}, "describe_security_groups"
            )
            main()

        assert exc_info.value.code == 1
