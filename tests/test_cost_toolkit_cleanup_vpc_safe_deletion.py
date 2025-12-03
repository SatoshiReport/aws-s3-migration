"""Tests for aws_vpc_safe_deletion helpers."""

from __future__ import annotations

from unittest.mock import patch

from botocore.exceptions import ClientError

from cost_toolkit.scripts.cleanup import aws_vpc_safe_deletion


@patch("cost_toolkit.scripts.cleanup.aws_vpc_safe_deletion.delete_vpc_and_dependencies")
def test_delete_vpc_and_dependencies_with_logging_success(mock_delete):
    """Returns True when underlying delete succeeds."""
    mock_delete.return_value = True

    result = aws_vpc_safe_deletion.delete_vpc_and_dependencies_with_logging("vpc-1", "us-east-1")

    assert result is True
    mock_delete.assert_called_once_with("vpc-1", region_name="us-east-1")


@patch("cost_toolkit.scripts.cleanup.aws_vpc_safe_deletion.delete_vpc_and_dependencies")
def test_delete_vpc_and_dependencies_with_logging_handles_error(mock_delete):
    """ClientError should be converted to False."""
    mock_delete.side_effect = ClientError(
        {"Error": {"Code": "UnauthorizedOperation"}},
        "DeleteVpc",
    )

    result = aws_vpc_safe_deletion.delete_vpc_and_dependencies_with_logging("vpc-2", "us-east-1")

    assert result is False


def test_delete_vpcs_collects_results(monkeypatch):
    """delete_vpcs should aggregate success/failure results."""
    calls = []

    def fake_delete(vpc_id, region):
        calls.append((vpc_id, region))
        return vpc_id.endswith("success")

    monkeypatch.setattr(
        aws_vpc_safe_deletion, "delete_vpc_and_dependencies_with_logging", fake_delete
    )
    monkeypatch.setattr(aws_vpc_safe_deletion.WAIT_EVENT, "wait", lambda *_: None)

    safe_vpcs = [("vpc-success", "us-east-1"), ("vpc-fail", "us-west-2")]
    results = aws_vpc_safe_deletion.delete_vpcs(safe_vpcs)

    assert calls == safe_vpcs
    assert results == [
        ("vpc-success", "us-east-1", True),
        ("vpc-fail", "us-west-2", False),
    ]


def test_get_safe_vpcs_returns_expected_shape():
    """get_safe_vpcs should return a list of region tuples."""
    safe_vpcs = aws_vpc_safe_deletion.get_safe_vpcs()
    assert safe_vpcs
    for item in safe_vpcs:
        assert isinstance(item, tuple)
        assert len(item) == 2


def test_print_vpc_deletion_summary_outputs(capsys):
    """print_vpc_deletion_summary should summarize successes and failures."""
    results = [("vpc-1", "us-east-1", True), ("vpc-2", "us-west-2", False)]

    aws_vpc_safe_deletion.print_vpc_deletion_summary(results)

    captured = capsys.readouterr().out
    assert "DELETION SUMMARY" in captured
    assert "vpc-1 (us-east-1)" in captured
    assert "vpc-2 (us-west-2)" in captured


def test_main_runs_with_patched_helpers(monkeypatch, capsys):
    """Main should orchestrate deletion and summary when helpers are patched."""
    monkeypatch.setattr(aws_vpc_safe_deletion, "get_safe_vpcs", lambda: [("vpc-1", "us-east-1")])
    monkeypatch.setattr(
        aws_vpc_safe_deletion,
        "delete_vpcs",
        lambda safe_vpcs: [(safe_vpcs[0][0], safe_vpcs[0][1], True)],
    )
    monkeypatch.setattr(
        aws_vpc_safe_deletion,
        "print_vpc_deletion_summary",
        lambda results: print(f"summary {results}"),
    )

    aws_vpc_safe_deletion.main()

    captured = capsys.readouterr().out
    assert "summary" in captured
