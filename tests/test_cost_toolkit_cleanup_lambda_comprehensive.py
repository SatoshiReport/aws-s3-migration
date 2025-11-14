"""Comprehensive tests for aws_lambda_cleanup.py."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError

from cost_toolkit.scripts.cleanup.aws_lambda_cleanup import (
    delete_lambda_functions,
    setup_aws_credentials,
)


def test_setup_aws_credentials_calls_shared_setup():
    """Test that setup calls the shared utility."""
    with patch(
        "cost_toolkit.scripts.cleanup.aws_lambda_cleanup.aws_utils.setup_aws_credentials"
    ) as mock_setup:
        setup_aws_credentials()
        mock_setup.assert_called_once()


class TestDeleteLambdaFunctions:
    """Tests for delete_lambda_functions function."""

    def test_delete_functions(self, capsys):
        """Test deleting Lambda functions (single and multiple)."""
        with patch("cost_toolkit.scripts.cleanup.aws_lambda_cleanup.setup_aws_credentials"):
            with patch("boto3.client") as mock_client:
                mock_lambda = MagicMock()
                mock_lambda.list_functions.return_value = {
                    "Functions": [
                        {"FunctionName": "function-1"},
                        {"FunctionName": "function-2"},
                        {"FunctionName": "function-3"},
                    ]
                }
                mock_client.return_value = mock_lambda
                delete_lambda_functions()
        assert mock_lambda.delete_function.call_count == 9
        captured = capsys.readouterr()
        assert "Total Lambda functions deleted: 9" in captured.out

    def test_delete_no_functions(self, capsys):
        """Test when no Lambda functions exist."""
        with patch("cost_toolkit.scripts.cleanup.aws_lambda_cleanup.setup_aws_credentials"):
            with patch("boto3.client") as mock_client:
                mock_lambda = MagicMock()
                mock_lambda.list_functions.return_value = {"Functions": []}
                mock_client.return_value = mock_lambda
                delete_lambda_functions()
        captured = capsys.readouterr()
        assert "No Lambda functions found" in captured.out
        assert "No Lambda functions were deleted" in captured.out

    def test_delete_function_error(self, capsys):
        """Test handling error when deleting function."""
        with patch("cost_toolkit.scripts.cleanup.aws_lambda_cleanup.setup_aws_credentials"):
            with patch("boto3.client") as mock_client:
                mock_lambda = MagicMock()
                mock_lambda.list_functions.return_value = {
                    "Functions": [{"FunctionName": "test-function"}]
                }
                mock_lambda.delete_function.side_effect = ClientError(
                    {"Error": {"Code": "ServiceError"}}, "delete_function"
                )
                mock_client.return_value = mock_lambda
                delete_lambda_functions()
        captured = capsys.readouterr()
        assert "Failed to delete" in captured.out

    def test_list_functions_error(self, capsys):
        """Test handling error when listing functions."""
        with patch("cost_toolkit.scripts.cleanup.aws_lambda_cleanup.setup_aws_credentials"):
            with patch("boto3.client") as mock_client:
                mock_lambda = MagicMock()
                mock_lambda.list_functions.side_effect = ClientError(
                    {"Error": {"Code": "AccessDenied"}}, "list_functions"
                )
                mock_client.return_value = mock_lambda
                delete_lambda_functions()
        captured = capsys.readouterr()
        assert "Error accessing Lambda" in captured.out

    def test_multiple_regions(self, capsys):
        """Test processing multiple regions."""
        with patch("cost_toolkit.scripts.cleanup.aws_lambda_cleanup.setup_aws_credentials"):
            with patch("boto3.client") as mock_client:
                call_count = 0

                def list_functions_side_effect():
                    nonlocal call_count
                    call_count += 1
                    if call_count == 1:
                        return {"Functions": [{"FunctionName": "func-us-east-1"}]}
                    if call_count == 2:
                        return {"Functions": [{"FunctionName": "func-us-east-2"}]}
                    return {"Functions": [{"FunctionName": "func-us-west-2"}]}

                mock_lambda = MagicMock()
                mock_lambda.list_functions.side_effect = list_functions_side_effect
                mock_client.return_value = mock_lambda
                delete_lambda_functions()
        captured = capsys.readouterr()
        assert "us-east-1" in captured.out
        assert "us-east-2" in captured.out
        assert "us-west-2" in captured.out

    def test_summary_printed(self, capsys):
        """Test that summary is always printed."""
        with patch("cost_toolkit.scripts.cleanup.aws_lambda_cleanup.setup_aws_credentials"):
            with patch("boto3.client") as mock_client:
                mock_lambda = MagicMock()
                mock_lambda.list_functions.return_value = {"Functions": []}
                mock_client.return_value = mock_lambda
                delete_lambda_functions()
        captured = capsys.readouterr()
        assert "Lambda Cleanup Summary" in captured.out
        assert "Total Lambda functions deleted" in captured.out
