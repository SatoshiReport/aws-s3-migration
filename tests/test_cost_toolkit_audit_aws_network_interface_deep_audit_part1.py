"""Comprehensive tests for aws_network_interface_deep_audit.py - Part 1."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from cost_toolkit.scripts.audit.aws_network_interface_deep_audit import (
    _check_instance_attachment,
    _print_basic_eni_info,
)


class TestLoadAwsCredentials:
    """Tests for load_aws_credentials function."""

    def test_load_credentials_success(self, capsys):
        """Test successful credential loading from environment."""
        # This test is no longer relevant - load_aws_credentials wrapper has been removed
        # Module now uses setup_aws_credentials directly
        pass

    def test_load_credentials_missing_access_key(self):
        """Test credential loading with missing access key."""
        # This test is no longer relevant - load_aws_credentials wrapper has been removed
        # Module now uses setup_aws_credentials directly
        pass

    def test_load_credentials_missing_secret_key(self):
        """Test credential loading with missing secret key."""
        # This test is no longer relevant - load_aws_credentials wrapper has been removed
        # Module now uses setup_aws_credentials directly
        pass

    def test_load_credentials_both_missing(self):
        """Test credential loading with both credentials missing."""
        # This test is no longer relevant - load_aws_credentials wrapper has been removed
        # Module now uses setup_aws_credentials directly
        pass

    def test_load_dotenv_called(self):
        """Test that load_dotenv is called with correct path."""
        # This test is no longer relevant - load_aws_credentials wrapper has been removed
        # Module now uses setup_aws_credentials directly
        pass


class TestPrintBasicEniInfo:
    """Tests for _print_basic_eni_info function."""

    def test_print_basic_info_complete(self, capsys):
        """Test printing ENI info with all fields present."""
        eni = {
            "Status": "in-use",
            "InterfaceType": "interface",
            "Description": "Primary network interface",
            "VpcId": "vpc-12345",
            "SubnetId": "subnet-67890",
        }

        _print_basic_eni_info(eni)

        captured = capsys.readouterr()
        assert "Status: in-use" in captured.out
        assert "Type: interface" in captured.out
        assert "Description: Primary network interface" in captured.out
        assert "VPC: vpc-12345" in captured.out
        assert "Subnet: subnet-67890" in captured.out

    def test_print_basic_info_missing_optional_fields(self, capsys):
        """Test printing ENI info with missing optional fields."""
        eni = {
            "Status": "available",
        }

        _print_basic_eni_info(eni)

        captured = capsys.readouterr()
        assert "Status: available" in captured.out
        assert "Type: interface" in captured.out
        assert "Description: No description" in captured.out
        assert "VPC: N/A" in captured.out
        assert "Subnet: N/A" in captured.out

    def test_print_basic_info_special_interface_type(self, capsys):
        """Test printing ENI info with special interface type."""
        eni = {
            "Status": "in-use",
            "InterfaceType": "nat_gateway",
            "Description": "NAT Gateway interface",
            "VpcId": "vpc-abc",
            "SubnetId": "subnet-xyz",
        }

        _print_basic_eni_info(eni)

        captured = capsys.readouterr()
        assert "Type: nat_gateway" in captured.out

    def test_print_basic_info_empty_description(self, capsys):
        """Test printing ENI info with empty description."""
        eni = {
            "Status": "in-use",
            "Description": "",
        }

        _print_basic_eni_info(eni)

        captured = capsys.readouterr()
        assert "Description:" in captured.out


class TestCheckInstanceAttachmentActiveStates:
    """Tests for _check_instance_attachment with active instance states."""

    def test_check_attachment_no_instance_id(self, capsys):
        """Test attachment check with no instance ID."""
        ec2 = MagicMock()
        attachment = {
            "Status": "attached",
            "AttachTime": "2024-01-01T00:00:00Z",
        }

        result = _check_instance_attachment(ec2, attachment)

        assert result is None
        captured = capsys.readouterr()
        assert "Attachment Status: attached" in captured.out
        assert "Attach Time: 2024-01-01T00:00:00Z" in captured.out
        ec2.describe_instances.assert_not_called()

    def test_check_attachment_instance_exists_running(self, capsys):
        """Test attachment check with running instance."""
        ec2 = MagicMock()
        ec2.describe_instances.return_value = {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "State": {"Name": "running"},
                            "InstanceType": "t2.micro",
                        }
                    ]
                }
            ]
        }

        attachment = {
            "InstanceId": "i-123456",
            "Status": "attached",
            "AttachTime": "2024-01-01T00:00:00Z",
        }

        result = _check_instance_attachment(ec2, attachment)

        assert result == "active"
        captured = capsys.readouterr()
        assert "Instance exists: i-123456" in captured.out
        assert "Instance State: running" in captured.out
        assert "Instance Type: t2.micro" in captured.out
        assert "Instance is active" in captured.out
        ec2.describe_instances.assert_called_once_with(InstanceIds=["i-123456"])

    def test_check_attachment_instance_pending(self, capsys):
        """Test attachment check with pending instance."""
        ec2 = MagicMock()
        ec2.describe_instances.return_value = {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "State": {"Name": "pending"},
                            "InstanceType": "t2.micro",
                        }
                    ]
                }
            ]
        }

        attachment = {
            "InstanceId": "i-pending",
            "Status": "attached",
            "AttachTime": "2024-01-01T00:00:00Z",
        }

        result = _check_instance_attachment(ec2, attachment)

        assert result == "active"
        captured = capsys.readouterr()
        assert "Instance is active" in captured.out


class TestCheckInstanceAttachmentEdgeCases:
    """Tests for _check_instance_attachment edge cases and missing fields."""

    def test_check_attachment_missing_status(self, capsys):
        """Test attachment check with missing status field."""
        ec2 = MagicMock()
        ec2.describe_instances.return_value = {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "State": {"Name": "running"},
                            "InstanceType": "t2.micro",
                        }
                    ]
                }
            ]
        }

        attachment = {
            "InstanceId": "i-123",
            "AttachTime": "2024-01-01T00:00:00Z",
        }

        result = _check_instance_attachment(ec2, attachment)

        assert result == "active"
        captured = capsys.readouterr()
        assert "Attachment Status: detached" in captured.out

    def test_check_attachment_missing_attach_time(self, capsys):
        """Test attachment check with missing attach time."""
        ec2 = MagicMock()
        ec2.describe_instances.return_value = {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "State": {"Name": "running"},
                            "InstanceType": "t2.micro",
                        }
                    ]
                }
            ]
        }

        attachment = {
            "InstanceId": "i-123",
            "Status": "attached",
        }

        result = _check_instance_attachment(ec2, attachment)

        assert result == "active"
        captured = capsys.readouterr()
        assert "Attach Time: Unknown" in captured.out
