"""Tests for ``update_rds_security_group`` helper behaviour."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from cost_toolkit.scripts.rds import update_rds_security_group as rds_update

# pylint: disable=protected-access


class _FakeResponse:
    """Simple HTTP response stand-in."""

    def __init__(self, status: int, body: bytes):
        """Capture the HTTP status code and response payload."""
        self.status = status
        self._body = body

    def read(self) -> bytes:
        """Return the mocked response body."""
        return self._body


class _FakeConnection:
    """Minimal HTTPSConnection stand-in that records the last request."""

    def __init__(self, response: _FakeResponse):
        """Initialize with a predetermined response."""
        self._response = response
        self._method = None
        self._path = None

    def request(self, method, path):
        """Record the issued method and endpoint."""
        self._method = method
        self._path = path

    def getresponse(self):
        """Return the fake response previously configured."""
        return self._response

    def close(self):
        """No-op close for compatibility."""


@patch("cost_toolkit.scripts.rds.update_rds_security_group.http.client.HTTPSConnection")
def test_fetch_current_ip_success(mock_conn):
    """Return the parsed IP when the HTTP endpoint responds OK."""
    response = _FakeResponse(200, b"1.2.3.4\n")
    mock_instance = _FakeConnection(response)
    mock_conn.return_value = mock_instance

    result = rds_update._fetch_current_ip()

    assert result == "1.2.3.4"
    mock_conn.assert_called_once_with("ipv4.icanhazip.com", timeout=10)


@patch("cost_toolkit.scripts.rds.update_rds_security_group.http.client.HTTPSConnection")
def test_fetch_current_ip_http_error(mock_conn):
    """Raise when the HTTP client cannot reach the endpoint."""
    mock_conn.side_effect = OSError("network")
    with pytest.raises(rds_update.PublicIPRetrievalError):
        rds_update._fetch_current_ip()


@patch("cost_toolkit.scripts.rds.update_rds_security_group.http.client.HTTPSConnection")
def test_fetch_current_ip_bad_status(mock_conn):
    """Raise when the HTTP service responds with a non-2xx status."""
    response = _FakeResponse(500, b"")
    mock_conn.return_value = _FakeConnection(response)
    with pytest.raises(rds_update.PublicIPRetrievalError):
        rds_update._fetch_current_ip()
