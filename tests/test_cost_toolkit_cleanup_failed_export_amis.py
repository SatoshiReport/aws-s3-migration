"""Tests for aws_cleanup_failed_export_amis script."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError

from cost_toolkit.scripts.cleanup.aws_cleanup_failed_export_amis import (
    cleanup_failed_export_amis,
    main,
)


class TestCleanupFailedExportAMIsSuccess:
    """Test successful cleanup scenarios for failed export AMIs."""

    def test_cleanup_all_amis_success(self, capsys):
        """Test successful cleanup of all AMIs."""
        with patch("boto3.client") as mock_client:
            mock_ec2 = MagicMock()
            mock_ec2.describe_images.return_value = {"Images": [{"ImageId": "ami-123"}]}
            mock_ec2.deregister_image.return_value = {}
            mock_client.return_value = mock_ec2
            cleanup_failed_export_amis()
            captured = capsys.readouterr()
            assert "AWS Failed Export AMI Cleanup" in captured.out
            assert "Successfully cleaned up: 3 AMIs" in captured.out
            assert "Failed to clean up: 0 AMIs" in captured.out
            assert "Failed export AMI cleanup completed!" in captured.out
            assert mock_ec2.deregister_image.call_count == 3

    def test_cleanup_mixed_results(self, capsys):
        """Test cleanup with mixed success and failure results."""
        with patch("boto3.client") as mock_client:
            mock_ec2 = MagicMock()
            call_count = [0]

            def describe_images_side_effect(**_kwargs):
                return {"Images": [{"ImageId": _kwargs["ImageIds"][0]}]}

            def deregister_side_effect(**_kwargs):
                call_count[0] += 1
                if call_count[0] == 1:
                    return {}
                if call_count[0] == 2:
                    raise ClientError(
                        {"Error": {"Code": "InvalidAMIID.Unavailable"}}, "deregister_image"
                    )
                return {}

            mock_ec2.describe_images.side_effect = describe_images_side_effect
            mock_ec2.deregister_image.side_effect = deregister_side_effect
            mock_client.return_value = mock_ec2
            cleanup_failed_export_amis()
            captured = capsys.readouterr()
            assert "Successfully cleaned up: 2 AMIs" in captured.out
            assert "Failed to clean up: 1 AMIs" in captured.out

    def test_cleanup_partial_already_deleted(self, capsys):
        """Test cleanup when some AMIs are already deleted."""
        with patch("boto3.client") as mock_client:
            mock_ec2 = MagicMock()
            call_count = [0]

            def describe_images_side_effect(**kwargs):
                call_count[0] += 1
                if call_count[0] == 1:
                    return {"Images": []}
                return {"Images": [{"ImageId": kwargs["ImageIds"][0]}]}

            mock_ec2.describe_images.side_effect = describe_images_side_effect
            mock_ec2.deregister_image.return_value = {}
            mock_client.return_value = mock_ec2
            cleanup_failed_export_amis()
            captured = capsys.readouterr()
            assert "no longer exists" in captured.out
            assert "Successfully cleaned up: 2 AMIs" in captured.out
            assert mock_ec2.deregister_image.call_count == 2


class TestCleanupFailedExportAMIsErrors:
    """Test error handling for failed export AMI cleanup."""

    def test_cleanup_ami_already_deleted(self, capsys):
        """Test handling of AMIs already deleted."""
        with patch("boto3.client") as mock_client:
            mock_ec2 = MagicMock()
            mock_ec2.describe_images.return_value = {"Images": []}
            mock_client.return_value = mock_ec2
            cleanup_failed_export_amis()
            captured = capsys.readouterr()
            assert "no longer exists" in captured.out
            assert mock_ec2.deregister_image.call_count == 0

    def test_cleanup_ami_deregister_error(self, capsys):
        """Test handling of errors during AMI deregistration."""
        with patch("boto3.client") as mock_client:
            mock_ec2 = MagicMock()
            mock_ec2.describe_images.return_value = {"Images": [{"ImageId": "ami-123"}]}
            error = ClientError(
                {"Error": {"Code": "InvalidAMIID.Unavailable", "Message": "AMI unavailable"}},
                "deregister_image",
            )
            mock_ec2.deregister_image.side_effect = error
            mock_client.return_value = mock_ec2
            cleanup_failed_export_amis()
            captured = capsys.readouterr()
            assert "Error cleaning up" in captured.out
            assert "Successfully cleaned up: 0 AMIs" in captured.out
            assert "Failed to clean up: 3 AMIs" in captured.out


class TestCleanupFailedExportAMIsConfiguration:
    """Test configuration and setup for failed export AMI cleanup."""

    def test_cleanup_uses_correct_regions(self):
        """Test that cleanup uses correct regions for each AMI."""
        with patch("boto3.client") as mock_client:
            mock_ec2 = MagicMock()
            mock_ec2.describe_images.return_value = {"Images": [{"ImageId": "ami-123"}]}
            mock_ec2.deregister_image.return_value = {}
            mock_client.return_value = mock_ec2
            cleanup_failed_export_amis()
            calls = mock_client.call_args_list
            regions = [call[1]["region_name"] for call in calls]
            assert regions.count("eu-west-2") == 2
            assert regions.count("us-east-2") == 1

    def test_cleanup_uses_credentials(self):
        """Test that cleanup uses provided credentials."""
        with patch("boto3.client") as mock_client:
            mock_ec2 = MagicMock()
            mock_ec2.describe_images.return_value = {"Images": [{"ImageId": "ami-123"}]}
            mock_ec2.deregister_image.return_value = {}
            mock_client.return_value = mock_ec2
            cleanup_failed_export_amis()
            for call_args in mock_client.call_args_list:
                assert "aws_access_key_id" in call_args[1]
                assert "aws_secret_access_key" in call_args[1]

    def test_cleanup_displays_ami_info(self, capsys):
        """Test that cleanup displays AMI information."""
        with patch("boto3.client") as mock_client:
            mock_ec2 = MagicMock()
            mock_ec2.describe_images.return_value = {"Images": [{"ImageId": "ami-123"}]}
            mock_ec2.deregister_image.return_value = {}
            mock_client.return_value = mock_ec2
            cleanup_failed_export_amis()
            captured = capsys.readouterr()
            assert "ami-0fb32d09d4167dc8b" in captured.out
            assert "ami-0311aad3c728f520b" in captured.out
            assert "ami-0fa8c0016d1e40180" in captured.out
            assert "eu-west-2" in captured.out
            assert "us-east-2" in captured.out

    def test_cleanup_displays_descriptions(self, capsys):
        """Test that cleanup displays AMI descriptions."""
        with patch("boto3.client") as mock_client:
            mock_ec2 = MagicMock()
            mock_ec2.describe_images.return_value = {"Images": [{"ImageId": "ami-123"}]}
            mock_ec2.deregister_image.return_value = {}
            mock_client.return_value = mock_ec2
            cleanup_failed_export_amis()
            captured = capsys.readouterr()
            assert "snap-0f68820355c25e73e export AMI" in captured.out
            assert "snap-046b7eace8694913b export AMI" in captured.out
            assert "snap-036eee4a7c291fd26 export AMI" in captured.out

    def test_cleanup_calls_deregister_for_each_ami(self):
        """Test that deregister is called for each AMI."""
        with patch("boto3.client") as mock_client:
            mock_ec2 = MagicMock()
            mock_ec2.describe_images.return_value = {"Images": [{"ImageId": "ami-123"}]}
            mock_ec2.deregister_image.return_value = {}
            mock_client.return_value = mock_ec2
            cleanup_failed_export_amis()
            deregister_calls = mock_ec2.deregister_image.call_args_list
            assert len(deregister_calls) == 3
            ami_ids = [call[1]["ImageId"] for call in deregister_calls]
            assert "ami-0fb32d09d4167dc8b" in ami_ids
            assert "ami-0311aad3c728f520b" in ami_ids
            assert "ami-0fa8c0016d1e40180" in ami_ids


class TestMain:
    """Test main execution function."""

    def test_main_success(self, capsys):
        """Test successful main execution."""
        with patch("cost_toolkit.common.credential_utils.setup_aws_credentials") as mock_load:
            mock_load.return_value = ("key", "secret")
            with patch("boto3.client") as mock_client:
                mock_ec2 = MagicMock()
                mock_ec2.describe_images.return_value = {"Images": [{"ImageId": "ami-123"}]}
                mock_ec2.deregister_image.return_value = {}
                mock_client.return_value = mock_ec2
                main()
                captured = capsys.readouterr()
                assert "Successfully cleaned up: 3 AMIs" in captured.out

    def test_main_client_error(self, capsys):
        """Test main with ClientError during execution."""
        with patch("cost_toolkit.common.credential_utils.setup_aws_credentials") as mock_load:
            error = ClientError({"Error": {"Code": "ServiceUnavailable"}}, "client")
            mock_load.side_effect = error
            try:
                main()
                assert False, "Should have raised ClientError and exited"
            except SystemExit as e:
                assert e.code == 1
                captured = capsys.readouterr()
                assert "Script failed" in captured.out

    def test_main_calls_cleanup(self):
        """Test that main calls cleanup_failed_export_amis."""
        with patch(
            "cost_toolkit.scripts.cleanup.aws_cleanup_failed_export_amis.cleanup_failed_export_amis"
        ) as mock_cleanup:
            with patch("cost_toolkit.common.credential_utils.setup_aws_credentials") as mock_load:
                mock_load.return_value = ("key", "secret")
                try:
                    main()
                except SystemExit:
                    pass
                mock_cleanup.assert_called_once()

    def test_main_with_partial_success(self, capsys):
        """Test main with partial cleanup success."""
        with patch("cost_toolkit.common.credential_utils.setup_aws_credentials") as mock_load:
            mock_load.return_value = ("key", "secret")
            with patch("boto3.client") as mock_client:
                mock_ec2 = MagicMock()
                call_count = [0]

                def describe_side_effect(**_kwargs):
                    return {"Images": [{"ImageId": _kwargs["ImageIds"][0]}]}

                def deregister_side_effect(**_kwargs):
                    call_count[0] += 1
                    if call_count[0] == 1:
                        return {}
                    raise ClientError(
                        {"Error": {"Code": "InvalidAMIID.Unavailable"}}, "deregister_image"
                    )

                mock_ec2.describe_images.side_effect = describe_side_effect
                mock_ec2.deregister_image.side_effect = deregister_side_effect
                mock_client.return_value = mock_ec2
                main()
                captured = capsys.readouterr()
                assert "Successfully cleaned up: 1 AMIs" in captured.out
                assert "Failed to clean up: 2 AMIs" in captured.out
