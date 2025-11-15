"""Tests for cost_toolkit/common/credential_utils.py"""

from __future__ import annotations

from unittest.mock import patch

from cost_toolkit.common.credential_utils import (
    check_aws_credentials,
    setup_aws_credentials,
)
from tests.assertions import assert_equal


@patch("os.getenv")
@patch("cost_toolkit.scripts.aws_client_factory.load_dotenv")
@patch("builtins.print")
def test_setup_aws_credentials_success(mock_print, mock_load_dotenv, mock_getenv):
    """Test setup_aws_credentials with valid credentials."""

    def getenv_side_effect(key):
        return {"AWS_ACCESS_KEY_ID": "test_key", "AWS_SECRET_ACCESS_KEY": "test_secret"}.get(key)

    mock_getenv.side_effect = getenv_side_effect

    key_id, secret = setup_aws_credentials()

    assert_equal(key_id, "test_key")
    assert_equal(secret, "test_secret")
    mock_load_dotenv.assert_called_once()
    mock_print.assert_called_once()


@patch("os.getenv")
@patch("cost_toolkit.scripts.aws_client_factory.load_dotenv")
def test_setup_aws_credentials_missing(mock_load_dotenv, mock_getenv):
    """Test setup_aws_credentials with missing credentials."""
    mock_getenv.return_value = None

    try:
        setup_aws_credentials()
        assert False, "Expected ValueError to be raised"
    except ValueError as e:
        assert "AWS credentials not found" in str(e)

    mock_load_dotenv.assert_called_once()


@patch("os.getenv")
@patch("cost_toolkit.scripts.aws_client_factory.load_dotenv")
def test_check_aws_credentials_success(mock_load_dotenv, mock_getenv):
    """Test check_aws_credentials with valid credentials."""

    def getenv_side_effect(key):
        return {"AWS_ACCESS_KEY_ID": "test_key", "AWS_SECRET_ACCESS_KEY": "test_secret"}.get(key)

    mock_getenv.side_effect = getenv_side_effect

    result = check_aws_credentials()

    assert_equal(result, True)
    mock_load_dotenv.assert_called_once()


@patch("os.getenv")
@patch("cost_toolkit.scripts.aws_client_factory.load_dotenv")
@patch("builtins.print")
def test_check_aws_credentials_missing(mock_print, mock_load_dotenv, mock_getenv):
    """Test check_aws_credentials with missing credentials."""
    mock_getenv.return_value = None

    result = check_aws_credentials()

    assert_equal(result, False)
    mock_load_dotenv.assert_called_once()
    # Should print helpful error message
    assert mock_print.call_count >= 1
