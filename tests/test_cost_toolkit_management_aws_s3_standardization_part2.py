"""Comprehensive tests for aws_s3_standardization.py - Part 2 (Main Functions)."""

from __future__ import annotations

from unittest.mock import patch

from botocore.exceptions import ClientError, NoCredentialsError

from cost_toolkit.scripts.management.aws_s3_standardization import (
    EXCLUDED_BUCKET,
    _process_single_bucket,
    main,
    standardize_s3_buckets,
)


def _verify_bucket_processing(mock_ensure_private, mock_remove_lifecycle, mock_move_objects):
    """Verify all buckets were processed correctly."""
    assert mock_ensure_private.call_count == 3
    assert mock_remove_lifecycle.call_count == 3
    assert mock_move_objects.call_count == 3


def _verify_excluded_bucket(mock_ensure_private):
    """Verify excluded bucket was not processed."""
    call_names = [call[0][0] for call in mock_ensure_private.call_args_list]
    assert "bucket1" in call_names
    assert "bucket2" in call_names
    assert "bucket3" in call_names
    assert EXCLUDED_BUCKET not in call_names


def test_standardize_multiple_buckets(capsys):
    """Test standardizing multiple buckets."""
    mod = "cost_toolkit.scripts.management.aws_s3_standardization"
    with (
        patch(f"{mod}.setup_aws_credentials"),
        patch(f"{mod}.list_buckets") as mock_list_buckets,
        patch(f"{mod}.get_bucket_region") as mock_get_region,
        patch(f"{mod}.ensure_bucket_private") as mock_ensure_private,
        patch(f"{mod}.remove_lifecycle_policy") as mock_remove_lifecycle,
        patch(f"{mod}.move_objects_to_standard_storage") as mock_move_objects,
    ):
        mock_list_buckets.return_value = [
            {"Name": "bucket1"},
            {"Name": "bucket2"},
            {"Name": EXCLUDED_BUCKET},
            {"Name": "bucket3"},
        ]
        mock_get_region.return_value = "us-east-1"
        mock_ensure_private.return_value = True
        mock_remove_lifecycle.return_value = True
        mock_move_objects.return_value = True

        standardize_s3_buckets()

        _verify_bucket_processing(mock_ensure_private, mock_remove_lifecycle, mock_move_objects)
        _verify_excluded_bucket(mock_ensure_private)

        captured = capsys.readouterr()
        assert "S3 STANDARDIZATION COMPLETE" in captured.out
        assert f"Excluding {EXCLUDED_BUCKET}" in captured.out


def test_standardize_different_regions():
    """Test standardizing buckets in different regions."""
    mod = "cost_toolkit.scripts.management.aws_s3_standardization"
    with (
        patch(f"{mod}.setup_aws_credentials"),
        patch(f"{mod}.list_buckets") as mock_list_buckets,
        patch(f"{mod}.get_bucket_region") as mock_get_region,
        patch(f"{mod}.ensure_bucket_private") as mock_ensure_private,
        patch(f"{mod}.remove_lifecycle_policy") as mock_remove_lifecycle,
        patch(f"{mod}.move_objects_to_standard_storage") as mock_move_objects,
    ):
        mock_list_buckets.return_value = [
            {"Name": "us-bucket"},
            {"Name": "eu-bucket"},
        ]
        mock_get_region.side_effect = ["us-east-1", "eu-west-1"]
        mock_ensure_private.return_value = True
        mock_remove_lifecycle.return_value = True
        mock_move_objects.return_value = True

        standardize_s3_buckets()

        region_calls = [call[0][1] for call in mock_ensure_private.call_args_list]
        assert "us-east-1" in region_calls
        assert "eu-west-1" in region_calls


def test_standardize_continues_on_error(capsys):
    """Test that standardization continues even if one operation fails."""
    mod = "cost_toolkit.scripts.management.aws_s3_standardization"
    with (
        patch(f"{mod}.setup_aws_credentials"),
        patch(f"{mod}.list_buckets") as mock_list_buckets,
        patch(f"{mod}.get_bucket_region") as mock_get_region,
        patch(f"{mod}.ensure_bucket_private") as mock_ensure_private,
        patch(f"{mod}.remove_lifecycle_policy") as mock_remove_lifecycle,
        patch(f"{mod}.move_objects_to_standard_storage") as mock_move_objects,
    ):
        mock_list_buckets.return_value = [
            {"Name": "bucket1"},
            {"Name": "bucket2"},
        ]
        mock_get_region.return_value = "us-east-1"
        mock_ensure_private.side_effect = [False, True]
        mock_remove_lifecycle.return_value = True
        mock_move_objects.return_value = True

        standardize_s3_buckets()

        assert mock_ensure_private.call_count == 2
        assert mock_remove_lifecycle.call_count == 2
        assert mock_move_objects.call_count == 2
        captured = capsys.readouterr()
        assert "S3 STANDARDIZATION COMPLETE" in captured.out


class TestStandardizeS3BucketsErrors:
    """Tests for standardize_s3_buckets function - error handling."""

    @patch("cost_toolkit.scripts.management.aws_s3_standardization.setup_aws_credentials")
    @patch("cost_toolkit.scripts.management.aws_s3_standardization.list_buckets")
    def test_standardize_no_credentials(
        self,
        mock_list_buckets,
        _mock_setup_creds,
        capsys,
    ):
        """Test handling no credentials error."""
        mock_list_buckets.side_effect = NoCredentialsError()

        standardize_s3_buckets()

        captured = capsys.readouterr()
        assert "AWS credentials not found" in captured.out

    @patch("cost_toolkit.scripts.management.aws_s3_standardization.setup_aws_credentials")
    @patch("cost_toolkit.scripts.management.aws_s3_standardization.list_buckets")
    def test_standardize_client_error(
        self,
        mock_list_buckets,
        _mock_setup_creds,
        capsys,
    ):
        """Test handling AWS API error."""
        mock_list_buckets.side_effect = ClientError({"Error": {"Code": "AccessDenied"}}, "list_buckets")

        standardize_s3_buckets()

        captured = capsys.readouterr()
        assert "AWS API error" in captured.out


class TestStandardizeS3BucketsEdgeCases:
    """Tests for standardize_s3_buckets function - edge cases."""

    @patch("cost_toolkit.scripts.management.aws_s3_standardization.setup_aws_credentials")
    @patch("cost_toolkit.scripts.management.aws_s3_standardization.list_buckets")
    def test_standardize_no_buckets(
        self,
        mock_list_buckets,
        _mock_setup_creds,
        capsys,
    ):
        """Test when no buckets exist."""
        mock_list_buckets.return_value = []

        standardize_s3_buckets()

        captured = capsys.readouterr()
        assert "No S3 buckets found" in captured.out

    @patch("cost_toolkit.scripts.management.aws_s3_standardization.setup_aws_credentials")
    @patch("cost_toolkit.scripts.management.aws_s3_standardization.list_buckets")
    def test_standardize_only_excluded_bucket(
        self,
        mock_list_buckets,
        _mock_setup_creds,
        capsys,
    ):
        """Test when only excluded bucket exists."""
        mock_list_buckets.return_value = [{"Name": EXCLUDED_BUCKET}]

        standardize_s3_buckets()

        captured = capsys.readouterr()
        assert f"Excluding {EXCLUDED_BUCKET}" in captured.out


class TestMain:
    """Tests for main function."""

    @patch("cost_toolkit.scripts.management.aws_s3_standardization.input")
    @patch("cost_toolkit.scripts.management.aws_s3_standardization.standardize_s3_buckets")
    def test_main_confirmed(self, mock_standardize, mock_input, capsys):
        """Test main function with user confirmation."""
        mock_input.return_value = "yes"

        main()

        mock_standardize.assert_called_once()
        captured = capsys.readouterr()
        assert "WARNING" in captured.out

    @patch("cost_toolkit.scripts.management.aws_s3_standardization.input")
    @patch("cost_toolkit.scripts.management.aws_s3_standardization.standardize_s3_buckets")
    def test_main_cancelled(self, mock_standardize, mock_input, capsys):
        """Test main function with user cancellation."""
        mock_input.return_value = "no"

        main()

        mock_standardize.assert_not_called()
        captured = capsys.readouterr()
        assert "Operation cancelled" in captured.out

    @patch("cost_toolkit.scripts.management.aws_s3_standardization.input")
    @patch("cost_toolkit.scripts.management.aws_s3_standardization.standardize_s3_buckets")
    def test_main_invalid_response(self, mock_standardize, mock_input, capsys):
        """Test main function with invalid response."""
        mock_input.return_value = "maybe"

        main()

        mock_standardize.assert_not_called()
        captured = capsys.readouterr()
        assert "Operation cancelled" in captured.out

    @patch("cost_toolkit.scripts.management.aws_s3_standardization.input")
    @patch("cost_toolkit.scripts.management.aws_s3_standardization.standardize_s3_buckets")
    def test_main_case_insensitive(self, mock_standardize, mock_input):
        """Test main function accepts YES in any case."""
        mock_input.return_value = "YES"

        main()

        mock_standardize.assert_called_once()


@patch("cost_toolkit.scripts.management.aws_s3_standardization.ensure_bucket_private")
@patch("cost_toolkit.scripts.management.aws_s3_standardization.remove_lifecycle_policy")
@patch("cost_toolkit.scripts.management.aws_s3_standardization.move_objects_to_standard_storage")
def test_process_single_bucket(mock_move_objects, mock_remove_lifecycle, mock_ensure_private, capsys):
    """Test processing a single bucket through all steps."""
    mock_ensure_private.return_value = True
    mock_remove_lifecycle.return_value = True
    mock_move_objects.return_value = True

    _process_single_bucket("test-bucket", "us-east-1")

    mock_ensure_private.assert_called_once_with("test-bucket", "us-east-1")
    mock_remove_lifecycle.assert_called_once_with("test-bucket", "us-east-1")
    mock_move_objects.assert_called_once_with("test-bucket", "us-east-1")

    captured = capsys.readouterr()
    assert "Processing bucket: test-bucket" in captured.out
    assert "Ensuring bucket is private" in captured.out
    assert "Removing lifecycle policy" in captured.out
    assert "Converting objects to Standard storage" in captured.out
