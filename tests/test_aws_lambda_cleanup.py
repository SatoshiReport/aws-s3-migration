"""Tests for `aws_lambda_cleanup.delete_lambda_functions` flows."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError

from cost_toolkit.scripts.cleanup import aws_lambda_cleanup as lambda_cleanup


@patch("cost_toolkit.scripts.cleanup.aws_lambda_cleanup._WAIT_EVENT.wait")
@patch("cost_toolkit.scripts.aws_utils.setup_aws_credentials")
@patch(
    "cost_toolkit.scripts.cleanup.aws_lambda_cleanup.get_all_aws_regions",
    return_value=["us-east-1"],
)
@patch("cost_toolkit.scripts.cleanup.aws_lambda_cleanup.create_client")
def test_delete_lambda_functions_no_functions(mock_create_client, _, __, mock_wait, capsys):
    """Assert no errors when no Lambda functions are returned by AWS."""
    mock_lambda = MagicMock()
    mock_lambda.list_functions.return_value = {"Functions": []}
    mock_create_client.return_value = mock_lambda

    lambda_cleanup.delete_lambda_functions()

    captured = capsys.readouterr()
    assert "No Lambda functions were deleted" in captured.out
    mock_wait.assert_not_called()


@patch("cost_toolkit.scripts.cleanup.aws_lambda_cleanup._WAIT_EVENT.wait")
@patch("cost_toolkit.scripts.aws_utils.setup_aws_credentials")
@patch(
    "cost_toolkit.scripts.cleanup.aws_lambda_cleanup.get_all_aws_regions",
    return_value=["us-east-1"],
)
@patch("cost_toolkit.scripts.cleanup.aws_lambda_cleanup.create_client")
def test_delete_lambda_functions_with_failures(mock_create_client, _, __, mock_wait, capsys):
    """Ensure failures are reported and successes confirmed."""
    mock_lambda = MagicMock()
    mock_lambda.list_functions.return_value = {
        "Functions": [{"FunctionName": "fn-1"}, {"FunctionName": "fn-2"}]
    }

    def delete_side_effect(*_args, **kwargs):
        if kwargs["FunctionName"] == "fn-1":
            raise ClientError({"Error": {"Code": "AccessDenied"}}, "delete_function")

    mock_lambda.delete_function.side_effect = delete_side_effect
    mock_create_client.return_value = mock_lambda

    lambda_cleanup.delete_lambda_functions()

    captured = capsys.readouterr()
    assert "Failed to delete fn-1" in captured.out
    assert "Successfully deleted: fn-2" in captured.out
    mock_wait.assert_called_once()
