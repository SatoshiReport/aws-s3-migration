"""Tests for Lambda and EFS service checks in service_checks_extended."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import botocore.exceptions
from botocore.exceptions import ClientError

from cost_toolkit.scripts.billing.billing_report.service_checks_extended import (
    check_efs_status,
    check_lambda_status,
)


class TestCheckLambdaStatus:
    """Test Lambda service status checking."""

    def test_lambda_all_deleted(self):
        """Test status when all Lambda functions deleted."""
        with patch("boto3.client") as mock_client:
            mock_lambda = MagicMock()
            mock_lambda.list_functions.return_value = {"Functions": []}
            mock_client.return_value = mock_lambda
            is_resolved, message = check_lambda_status()
            assert is_resolved is True
            assert "RESOLVED" in message
            assert "All Lambda functions deleted" in message

    def test_lambda_functions_exist(self):
        """Test status when Lambda functions still exist."""
        with patch("boto3.client") as mock_client:
            mock_lambda = MagicMock()
            mock_lambda.list_functions.return_value = {
                "Functions": [
                    {"FunctionName": "func1"},
                    {"FunctionName": "func2"},
                    {"FunctionName": "func3"},
                ]
            }
            mock_client.return_value = mock_lambda
            is_resolved, message = check_lambda_status()
            assert is_resolved is False
            assert "ACTIVE" in message
            assert "9 Lambda functions still exist" in message

    def test_lambda_mixed_regions(self):
        """Test Lambda status across multiple regions."""
        with patch("boto3.client") as mock_client:
            mock_lambda = MagicMock()
            call_count = [0]

            def list_functions_side_effect():
                call_count[0] += 1
                if call_count[0] == 1:
                    return {"Functions": [{"FunctionName": "func1"}]}
                if call_count[0] == 2:
                    return {"Functions": [{"FunctionName": "func2"}]}
                return {"Functions": []}

            mock_lambda.list_functions.side_effect = list_functions_side_effect
            mock_client.return_value = mock_lambda
            is_resolved, message = check_lambda_status()
            assert is_resolved is False
            assert "2 Lambda functions still exist" in message

    def test_lambda_region_access_error(self):
        """Test Lambda status with region access errors."""
        with patch("boto3.client") as mock_client:
            mock_lambda = MagicMock()
            error = botocore.exceptions.ClientError(
                {"Error": {"Code": "AccessDenied"}}, "list_functions"
            )
            mock_lambda.list_functions.side_effect = error
            mock_client.return_value = mock_lambda
            is_resolved, message = check_lambda_status()
            assert is_resolved is True
            assert "RESOLVED" in message
            assert "All Lambda functions deleted" in message

    def test_lambda_client_error(self):
        """Test Lambda status with general ClientError."""
        with patch("boto3.client") as mock_client:
            error = ClientError({"Error": {"Code": "ServiceUnavailable"}}, "client")
            mock_client.side_effect = error
            is_resolved, message = check_lambda_status()
            assert is_resolved is True
            assert "RESOLVED" in message

    def test_lambda_partial_region_errors(self):
        """Test Lambda when some regions error but others succeed."""
        with patch("boto3.client") as mock_client:
            mock_lambda = MagicMock()
            call_count = [0]

            def list_functions_with_error():
                call_count[0] += 1
                if call_count[0] == 1:
                    raise botocore.exceptions.ClientError(
                        {"Error": {"Code": "AccessDenied"}}, "list_functions"
                    )
                return {"Functions": [{"FunctionName": "func1"}]}

            mock_lambda.list_functions.side_effect = list_functions_with_error
            mock_client.return_value = mock_lambda
            is_resolved, message = check_lambda_status()
            assert is_resolved is False
            assert "2 Lambda functions still exist" in message


class TestCheckEFSStatusSuccess:
    """Test EFS service status checking - success cases."""

    def test_efs_all_deleted(self):
        """Test status when all EFS file systems deleted."""
        with patch("boto3.client") as mock_client:
            mock_efs = MagicMock()
            mock_efs.describe_file_systems.return_value = {"FileSystems": []}
            mock_client.return_value = mock_efs
            is_resolved, message = check_efs_status()
            assert is_resolved is True
            assert "RESOLVED" in message
            assert "All EFS file systems deleted" in message

    def test_efs_file_systems_exist(self):
        """Test status when EFS file systems still exist."""
        with patch("boto3.client") as mock_client:
            mock_efs = MagicMock()
            mock_efs.describe_file_systems.return_value = {
                "FileSystems": [
                    {"FileSystemId": "fs-123"},
                    {"FileSystemId": "fs-456"},
                ]
            }
            mock_client.return_value = mock_efs
            is_resolved, message = check_efs_status()
            assert is_resolved is False
            assert "ACTIVE" in message
            assert "4 EFS file systems still exist" in message

    def test_efs_mixed_regions(self):
        """Test EFS status across multiple regions."""
        with patch("boto3.client") as mock_client:
            mock_efs = MagicMock()
            call_count = [0]

            def describe_side_effect():
                call_count[0] += 1
                if call_count[0] == 1:
                    return {"FileSystems": [{"FileSystemId": "fs-123"}]}
                return {"FileSystems": []}

            mock_efs.describe_file_systems.side_effect = describe_side_effect
            mock_client.return_value = mock_efs
            is_resolved, message = check_efs_status()
            assert is_resolved is False
            assert "1 EFS file systems still exist" in message

    def test_efs_single_file_system(self):
        """Test EFS status with single file system."""
        with patch("boto3.client") as mock_client:
            mock_efs = MagicMock()
            mock_efs.describe_file_systems.return_value = {
                "FileSystems": [{"FileSystemId": "fs-only"}]
            }
            mock_client.return_value = mock_efs
            is_resolved, message = check_efs_status()
            assert is_resolved is False
            assert "2 EFS file systems still exist" in message


class TestCheckEFSStatusErrors:
    """Test EFS service status checking - error cases."""

    def test_efs_region_access_error(self):
        """Test EFS status with region access errors."""
        with patch("boto3.client") as mock_client:
            mock_efs = MagicMock()
            error = botocore.exceptions.ClientError(
                {"Error": {"Code": "AccessDenied"}}, "describe_file_systems"
            )
            mock_efs.describe_file_systems.side_effect = error
            mock_client.return_value = mock_efs
            is_resolved, message = check_efs_status()
            assert is_resolved is True
            assert "RESOLVED" in message
            assert "All EFS file systems deleted" in message

    def test_efs_client_error(self):
        """Test EFS status with general ClientError."""
        with patch("boto3.client") as mock_client:
            error = ClientError({"Error": {"Code": "ServiceUnavailable"}}, "client")
            mock_client.side_effect = error
            is_resolved, message = check_efs_status()
            assert is_resolved is True
            assert "RESOLVED" in message

    def test_efs_partial_region_errors(self):
        """Test EFS when some regions error but others succeed."""
        with patch("boto3.client") as mock_client:
            mock_efs = MagicMock()
            call_count = [0]

            def describe_with_error():
                call_count[0] += 1
                if call_count[0] == 1:
                    raise botocore.exceptions.ClientError(
                        {"Error": {"Code": "AccessDenied"}}, "describe_file_systems"
                    )
                return {"FileSystems": [{"FileSystemId": "fs-123"}]}

            mock_efs.describe_file_systems.side_effect = describe_with_error
            mock_client.return_value = mock_efs
            is_resolved, message = check_efs_status()
            assert is_resolved is False
            assert "1 EFS file systems still exist" in message
