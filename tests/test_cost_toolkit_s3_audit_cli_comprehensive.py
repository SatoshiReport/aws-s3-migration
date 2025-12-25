"""Tests for cost_toolkit/scripts/audit/s3_audit/cli.py - comprehensive audit function"""

from __future__ import annotations

from collections import defaultdict
from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError, NoCredentialsError

from cost_toolkit.scripts.audit.s3_audit.cli import (
    audit_s3_comprehensive,
)


def test_audit_s3_comprehensive_success(capsys):
    """Test audit_s3_comprehensive with successful audit."""
    buckets = [{"Name": "test-bucket"}]

    bucket_analysis = {
        "bucket_name": "test-bucket",
        "total_objects": 100,
        "total_size_bytes": 1024**3,
    }

    with patch("cost_toolkit.scripts.audit.s3_audit.cli.setup_aws_credentials"):
        with patch("cost_toolkit.scripts.audit.s3_audit.cli.boto3.client") as mock_client:
            mock_s3 = MagicMock()
            mock_s3.list_buckets.return_value = {"Buckets": buckets}
            mock_client.return_value = mock_s3

            with patch(
                "cost_toolkit.scripts.audit.s3_audit.cli._process_all_buckets",
                return_value=(
                    [bucket_analysis],
                    defaultdict(lambda: {"count": 0, "size_bytes": 0, "cost": 0}),
                    [],
                    100,
                    1024**3,
                    23.0,
                ),
            ):
                with patch("cost_toolkit.scripts.audit.s3_audit.cli.print_overall_summary"):
                    breakdown_path = "cost_toolkit.scripts.audit.s3_audit.cli" + ".print_storage_class_breakdown"
                    optim_path = "cost_toolkit.scripts.audit.s3_audit.cli" + ".print_optimization_recommendations"
                    cleanup_path = "cost_toolkit.scripts.audit.s3_audit.cli" + ".print_cleanup_opportunities"
                    with patch(breakdown_path):
                        with patch(optim_path):
                            with patch(cleanup_path):
                                audit_s3_comprehensive()

    captured = capsys.readouterr()
    assert "AWS S3 Comprehensive Storage Audit" in captured.out
    assert "Found 1 S3 bucket(s) to analyze" in captured.out


def test_audit_s3_comprehensive_no_buckets(capsys):
    """Test audit_s3_comprehensive when no buckets exist."""
    with patch("cost_toolkit.scripts.audit.s3_audit.cli.setup_aws_credentials"):
        with patch("cost_toolkit.scripts.audit.s3_audit.cli.boto3.client") as mock_client:
            mock_s3 = MagicMock()
            mock_s3.list_buckets.return_value = {"Buckets": []}
            mock_client.return_value = mock_s3

            audit_s3_comprehensive()

    captured = capsys.readouterr()
    assert "No S3 buckets found in your account" in captured.out


def test_audit_s3_comprehensive_empty_buckets_response(capsys):
    """Test audit_s3_comprehensive when Buckets key is missing."""
    with patch("cost_toolkit.scripts.audit.s3_audit.cli.setup_aws_credentials"):
        with patch("cost_toolkit.scripts.audit.s3_audit.cli.boto3.client") as mock_client:
            mock_s3 = MagicMock()
            mock_s3.list_buckets.return_value = {}
            mock_client.return_value = mock_s3

            audit_s3_comprehensive()

    captured = capsys.readouterr()
    assert "No S3 buckets found in your account" in captured.out


def test_audit_s3_comprehensive_no_credentials_error(capsys):
    """Test audit_s3_comprehensive when credentials are not available."""
    with patch("cost_toolkit.scripts.audit.s3_audit.cli.setup_aws_credentials"):
        with patch("cost_toolkit.scripts.audit.s3_audit.cli.boto3.client") as mock_client:
            mock_client.side_effect = NoCredentialsError()

            audit_s3_comprehensive()

    captured = capsys.readouterr()
    assert "AWS credentials not found" in captured.out


def test_audit_s3_comprehensive_client_error(capsys):
    """Test audit_s3_comprehensive when AWS API returns an error."""
    error_response = {
        "Error": {
            "Code": "AccessDenied",
            "Message": "Access Denied",
        }
    }

    with patch("cost_toolkit.scripts.audit.s3_audit.cli.setup_aws_credentials"):
        with patch("cost_toolkit.scripts.audit.s3_audit.cli.boto3.client") as mock_client:
            mock_s3 = MagicMock()
            mock_s3.list_buckets.side_effect = ClientError(error_response, "ListBuckets")
            mock_client.return_value = mock_s3

            audit_s3_comprehensive()

    captured = capsys.readouterr()
    assert "AWS API error" in captured.out


def test_audit_s3_comprehensive_with_recommendations():
    """Test audit_s3_comprehensive with buckets that have recommendations."""
    buckets = [{"Name": "test-bucket"}]

    bucket_analysis = {
        "bucket_name": "test-bucket",
        "total_objects": 100,
        "total_size_bytes": 1024**3,
    }

    recommendations = [
        (
            "test-bucket",
            {
                "type": "lifecycle_policy",
                "description": "No lifecycle policy",
                "potential_savings": 10.0,
                "action": "Add lifecycle policy",
            },
        )
    ]

    storage_summary = defaultdict(lambda: {"count": 0, "size_bytes": 0, "cost": 0})
    storage_summary["STANDARD"] = {"count": 100, "size_bytes": 1024**3, "cost": 23.0}

    with patch("cost_toolkit.scripts.audit.s3_audit.cli.setup_aws_credentials"):
        mock_client_inst = MagicMock()
        mock_client_inst.list_buckets.return_value = {"Buckets": buckets}
        with patch(
            "cost_toolkit.scripts.audit.s3_audit.cli.boto3.client",
            return_value=mock_client_inst,
        ):
            with patch(
                "cost_toolkit.scripts.audit.s3_audit.cli._process_all_buckets",
                return_value=(
                    [bucket_analysis],
                    storage_summary,
                    recommendations,
                    100,
                    1024**3,
                    23.0,
                ),
            ):
                mock_overall = MagicMock()
                mock_storage = MagicMock()
                mock_optim = MagicMock()
                mock_cleanup = MagicMock()
                with patch(
                    "cost_toolkit.scripts.audit.s3_audit.cli.print_overall_summary",
                    mock_overall,
                ):
                    with patch(
                        "cost_toolkit.scripts.audit.s3_audit.cli.print_storage_class_breakdown",
                        mock_storage,
                    ):
                        with patch(
                            "cost_toolkit.scripts.audit.s3_audit.cli.print_optimization_recommendations",
                            mock_optim,
                        ):
                            with patch(
                                "cost_toolkit.scripts.audit.s3_audit.cli.print_cleanup_opportunities",
                                mock_cleanup,
                            ):
                                audit_s3_comprehensive()

    # Verify all print functions were called with correct data
    mock_overall.assert_called_once_with([bucket_analysis], 100, 1024**3, 23.0)
    mock_storage.assert_called_once_with(storage_summary, 1024**3)
    mock_optim.assert_called_once_with(recommendations)
    mock_cleanup.assert_called_once_with([bucket_analysis])
