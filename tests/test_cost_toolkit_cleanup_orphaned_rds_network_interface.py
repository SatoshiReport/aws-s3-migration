"""Tests for aws_orphaned_rds_network_interface_cleanup script."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError

from cost_toolkit.scripts.cleanup.aws_orphaned_rds_network_interface_cleanup import (
    EXPECTED_ORPHANED_INTERFACES_COUNT,
    delete_orphaned_rds_network_interfaces,
    main,
)


class TestDeleteOrphanedRDSNetworkInterfacesSuccess:
    """Test successful deletion scenarios for orphaned RDS network interfaces."""

    def test_delete_interfaces_success(self, capsys):
        """Test successful deletion of all orphaned interfaces."""
        with patch("boto3.client") as mock_client:
            mock_ec2 = MagicMock()
            mock_ec2.describe_network_interfaces.return_value = {
                "NetworkInterfaces": [{"Attachment": {}}]
            }
            mock_ec2.delete_network_interface.return_value = {}
            mock_client.return_value = mock_ec2
            deleted, failed = delete_orphaned_rds_network_interfaces("key_id", "secret_key")
            assert len(deleted) == 2
            assert len(failed) == 0
            captured = capsys.readouterr()
            assert "Successfully deleted" in captured.out

    def test_delete_interfaces_mixed_results(self):
        """Test mixed results with some successes and some failures."""
        with patch("boto3.client") as mock_client:
            mock_ec2 = MagicMock()
            call_count = [0]

            def delete_side_effect(**_kwargs):
                call_count[0] += 1
                if call_count[0] == 1:
                    return {}
                error = ClientError(
                    {
                        "Error": {
                            "Code": "InvalidNetworkInterfaceID.NotFound",
                            "Message": "Not found",
                        }
                    },
                    "delete_network_interface",
                )
                error.response = {
                    "Error": {"Code": "InvalidNetworkInterfaceID.NotFound", "Message": "Not found"}
                }
                raise error

            mock_ec2.describe_network_interfaces.return_value = {
                "NetworkInterfaces": [{"Attachment": {}}]
            }
            mock_ec2.delete_network_interface.side_effect = delete_side_effect
            mock_ec2.exceptions = MagicMock()
            mock_ec2.exceptions.ClientError = ClientError
            mock_client.return_value = mock_ec2
            deleted, failed = delete_orphaned_rds_network_interfaces("key_id", "secret_key")
            assert len(deleted) == 2
            assert len(failed) == 0

    def test_delete_interfaces_credentials_used(self):
        """Test that provided credentials are used correctly."""
        with patch("boto3.client") as mock_client:
            mock_ec2 = MagicMock()
            mock_ec2.describe_network_interfaces.return_value = {
                "NetworkInterfaces": [{"Attachment": {}}]
            }
            mock_ec2.delete_network_interface.return_value = {}
            mock_client.return_value = mock_ec2
            delete_orphaned_rds_network_interfaces("my_key_id", "my_secret_key")
            assert mock_client.call_count == 2
            for call_args in mock_client.call_args_list:
                assert call_args[1]["aws_access_key_id"] == "my_key_id"
                assert call_args[1]["aws_secret_access_key"] == "my_secret_key"


class TestDeleteOrphanedRDSNetworkInterfacesErrors:
    """Test error handling for orphaned RDS network interface deletion."""

    def test_delete_interfaces_already_deleted(self, capsys):
        """Test handling of interfaces already deleted."""
        with patch("boto3.client") as mock_client:
            mock_ec2 = MagicMock()
            mock_ec2.describe_network_interfaces.return_value = {
                "NetworkInterfaces": [{"Attachment": {}}]
            }
            error = ClientError(
                {"Error": {"Code": "InvalidNetworkInterfaceID.NotFound", "Message": "Not found"}},
                "delete_network_interface",
            )
            error.response = {
                "Error": {"Code": "InvalidNetworkInterfaceID.NotFound", "Message": "Not found"}
            }
            mock_ec2.delete_network_interface.side_effect = error
            mock_ec2.exceptions = MagicMock()
            mock_ec2.exceptions.ClientError = ClientError
            mock_client.return_value = mock_ec2
            deleted, failed = delete_orphaned_rds_network_interfaces("key_id", "secret_key")
            assert len(deleted) == 2
            assert len(failed) == 0
            captured = capsys.readouterr()
            assert "already deleted" in captured.out

    def test_delete_interfaces_in_use(self, capsys):
        """Test handling of interfaces still in use."""
        with patch("boto3.client") as mock_client:
            mock_ec2 = MagicMock()
            mock_ec2.describe_network_interfaces.return_value = {
                "NetworkInterfaces": [{"Attachment": {}}]
            }
            error = ClientError(
                {"Error": {"Code": "InvalidNetworkInterface.InUse", "Message": "In use"}},
                "delete_network_interface",
            )
            error.response = {
                "Error": {"Code": "InvalidNetworkInterface.InUse", "Message": "In use"}
            }
            mock_ec2.delete_network_interface.side_effect = error
            mock_ec2.exceptions = MagicMock()
            mock_ec2.exceptions.ClientError = ClientError
            mock_client.return_value = mock_ec2
            deleted, failed = delete_orphaned_rds_network_interfaces("key_id", "secret_key")
            assert len(deleted) == 0
            assert len(failed) == 2
            assert failed[0]["reason"] == "In use"
            captured = capsys.readouterr()
            assert "is in use" in captured.out

    def test_delete_interfaces_generic_error(self, capsys):
        """Test handling of generic deletion errors."""
        with patch("boto3.client") as mock_client:
            mock_ec2 = MagicMock()
            mock_ec2.describe_network_interfaces.return_value = {
                "NetworkInterfaces": [{"Attachment": {}}]
            }
            error = ClientError(
                {"Error": {"Code": "GenericError", "Message": "Something went wrong"}},
                "delete_network_interface",
            )
            error.response = {"Error": {"Code": "GenericError", "Message": "Something went wrong"}}
            mock_ec2.delete_network_interface.side_effect = error
            mock_ec2.exceptions = MagicMock()
            mock_ec2.exceptions.ClientError = ClientError
            mock_client.return_value = mock_ec2
            deleted, failed = delete_orphaned_rds_network_interfaces("key_id", "secret_key")
            assert len(deleted) == 0
            assert len(failed) == 2
            assert "Something went wrong" in failed[0]["reason"]
            captured = capsys.readouterr()
            assert "Failed to delete" in captured.out


def test_delete_interfaces_attached_to_instance(capsys):
    """Test skipping interfaces now attached to instances."""
    with patch("boto3.client") as mock_client:
        mock_ec2 = MagicMock()
        mock_ec2.describe_network_interfaces.return_value = {
            "NetworkInterfaces": [{"Attachment": {"InstanceId": "i-123"}}]
        }
        mock_client.return_value = mock_ec2
        deleted, failed = delete_orphaned_rds_network_interfaces("key_id", "secret_key")
        assert len(deleted) == 0
        assert len(failed) == 0
        captured = capsys.readouterr()
        assert "now attached to i-123" in captured.out
        assert mock_ec2.delete_network_interface.call_count == 0


class TestMain:
    """Test main execution function."""

    def test_main_user_cancels(self, capsys):
        """Test main when user cancels operation."""
        with patch("builtins.input", return_value="NO"):
            with patch(
                "cost_toolkit.scripts.cleanup.aws_orphaned_rds_network_interface_cleanup."
                "setup_aws_credentials"
            ) as mock_load:
                mock_load.return_value = ("key_id", "secret_key")
                main()
                captured = capsys.readouterr()
                assert "Operation cancelled" in captured.out

    def test_main_success(self, capsys):
        """Test successful main execution."""
        with patch("builtins.input", return_value="DELETE ORPHANED RDS INTERFACES"):
            with patch(
                "cost_toolkit.scripts.cleanup.aws_orphaned_rds_network_interface_cleanup."
                "setup_aws_credentials"
            ) as mock_load:
                mock_load.return_value = ("key_id", "secret_key")
                with patch("boto3.client") as mock_client:
                    mock_ec2 = MagicMock()
                    mock_ec2.describe_network_interfaces.return_value = {
                        "NetworkInterfaces": [{"Attachment": {}}]
                    }
                    mock_ec2.delete_network_interface.return_value = {}
                    mock_client.return_value = mock_ec2
                    main()
                    captured = capsys.readouterr()
                    assert "ORPHANED RDS NETWORK INTERFACE CLEANUP SUMMARY" in captured.out
                    assert "Successfully deleted: 2 interfaces" in captured.out
                    assert "Orphaned RDS network interface cleanup completed!" in captured.out

    def test_main_partial_success(self, capsys):
        """Test main with partial success."""
        with patch("builtins.input", return_value="DELETE ORPHANED RDS INTERFACES"):
            with patch(
                "cost_toolkit.scripts.cleanup.aws_orphaned_rds_network_interface_cleanup."
                "setup_aws_credentials"
            ) as mock_load:
                mock_load.return_value = ("key_id", "secret_key")
                with patch("boto3.client") as mock_client:
                    mock_ec2 = MagicMock()
                    call_count = [0]

                    def delete_side_effect(**_kwargs):
                        call_count[0] += 1
                        if call_count[0] == 1:
                            return {}
                        error = ClientError(
                            {
                                "Error": {
                                    "Code": "InvalidNetworkInterface.InUse",
                                    "Message": "In use",
                                }
                            },  # noqa: E501
                            "delete_network_interface",
                        )
                        error.response = {
                            "Error": {"Code": "InvalidNetworkInterface.InUse", "Message": "In use"}
                        }
                        raise error

                    mock_ec2.describe_network_interfaces.return_value = {
                        "NetworkInterfaces": [{"Attachment": {}}]
                    }
                    mock_ec2.delete_network_interface.side_effect = delete_side_effect
                    mock_ec2.exceptions = MagicMock()
                    mock_ec2.exceptions.ClientError = ClientError
                    mock_client.return_value = mock_ec2
                    main()
                    captured = capsys.readouterr()
                    assert "ORPHANED RDS NETWORK INTERFACE CLEANUP SUMMARY" in captured.out
                    assert "Successfully deleted: 1 interfaces" in captured.out
                    assert "Failed deletions: 1 interfaces" in captured.out

    def test_main_critical_error(self, capsys):
        """Test main with critical error during execution."""
        with patch("builtins.input", return_value="DELETE ORPHANED RDS INTERFACES"):
            with patch(
                "cost_toolkit.scripts.cleanup.aws_orphaned_rds_network_interface_cleanup."
                "setup_aws_credentials"
            ) as mock_load:
                error = ClientError(
                    {"Error": {"Code": "ServiceUnavailable"}}, "setup_aws_credentials"
                )
                mock_load.side_effect = error
                try:
                    main()
                    assert False, "Should have raised ClientError"
                except ClientError:
                    captured = capsys.readouterr()
                    assert "Critical error during cleanup" in captured.out


def test_expected_orphaned_interfaces_constant():
    """Test that the expected orphaned interfaces constant is correct."""
    assert EXPECTED_ORPHANED_INTERFACES_COUNT == 2
