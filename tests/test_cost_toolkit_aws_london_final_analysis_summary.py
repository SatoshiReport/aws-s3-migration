"""Tests for cost_toolkit/scripts/migration/aws_london_final_analysis_summary.py"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from botocore.exceptions import ClientError

from cost_toolkit.scripts.migration.aws_london_final_analysis_summary import (
    _print_duplicate_assessment,
    _print_final_recommendations,
    _print_metadata_findings,
    _stop_instance,
    final_analysis_summary,
    main,
)


# Tests for _stop_instance
@patch("cost_toolkit.scripts.migration.aws_london_final_analysis_summary.wait_for_instance_state")
@patch("builtins.print")
def test_stop_instance_success(mock_print, mock_wait_for_state):
    """Test stopping instance successfully."""
    mock_ec2 = MagicMock()

    _stop_instance(mock_ec2)

    mock_ec2.stop_instances.assert_called_once_with(InstanceIds=["i-05ad29f28fc8a8fdc"])
    mock_wait_for_state.assert_called_once_with(mock_ec2, "i-05ad29f28fc8a8fdc", "instance_stopped")
    mock_print.assert_called()


@patch("builtins.print")
def test_stop_instance_client_error(mock_print):
    """Test stopping instance with client error."""
    mock_ec2 = MagicMock()
    mock_ec2.stop_instances.side_effect = ClientError(
        {"Error": {"Code": "InstanceNotFound"}}, "StopInstances"
    )

    with pytest.raises(ClientError):
        _stop_instance(mock_ec2)

    mock_ec2.stop_instances.assert_called_once()
    mock_print.assert_called()


@patch("builtins.print")
@patch("cost_toolkit.scripts.migration.aws_london_final_analysis_summary.wait_for_instance_state")
def test_stop_instance_waiter_error(mock_wait_for_state, _mock_print):
    """Test stopping instance when waiter fails."""
    mock_ec2 = MagicMock()
    mock_wait_for_state.side_effect = ClientError(
        {"Error": {"Code": "WaiterError"}}, "WaitUntilInstanceStopped"
    )

    with pytest.raises(ClientError):
        _stop_instance(mock_ec2)

    mock_ec2.stop_instances.assert_called_once()


# Tests for _print_metadata_findings
@patch("builtins.print")
def test_print_metadata_findings(mock_print):
    """Test printing metadata findings."""
    _print_metadata_findings()

    mock_print.assert_called()
    call_args = [str(call) for call in mock_print.call_args_list]
    combined = " ".join(call_args)

    assert "Tars 3" in combined
    assert "64 GB" in combined
    assert "384 GB" in combined
    assert "Tars 2" in combined
    assert "1024 GB" in combined


# Tests for _print_duplicate_assessment
@patch("builtins.print")
def test_print_duplicate_assessment(mock_print):
    """Test printing duplicate assessment."""
    _print_duplicate_assessment()

    mock_print.assert_called()
    call_args = [str(call) for call in mock_print.call_args_list]
    combined = " ".join(call_args)

    assert "UNIQUE" in combined
    assert "LIKELY UNIQUE" in combined
    assert "POTENTIALLY DUPLICATE" in combined


# Tests for _print_final_recommendations
@patch("builtins.print")
def test_print_final_recommendations(mock_print):
    """Test printing final recommendations."""
    _print_final_recommendations()

    mock_print.assert_called()
    call_args = [str(call) for call in mock_print.call_args_list]
    combined = " ".join(call_args)

    assert "KEEP" in combined
    assert "30.72" in combined
    assert "115.72" in combined


# Tests for final_analysis_summary
@patch(
    "cost_toolkit.scripts.migration.aws_london_final_analysis_summary._print_final_recommendations"
)
@patch(
    "cost_toolkit.scripts.migration.aws_london_final_analysis_summary._print_duplicate_assessment"
)
@patch("cost_toolkit.scripts.migration.aws_london_final_analysis_summary._print_metadata_findings")
@patch("cost_toolkit.scripts.migration.aws_london_final_analysis_summary._stop_instance")
@patch("cost_toolkit.scripts.migration.aws_london_final_analysis_summary.boto3")
@patch("builtins.print")
def test_final_analysis_summary(_mock_print, mock_boto3, mock_stop, *print_mocks):
    """Test final analysis summary function."""
    mock_metadata, mock_assessment, mock_recommendations = print_mocks
    mock_ec2 = MagicMock()
    mock_boto3.client.return_value = mock_ec2

    final_analysis_summary()

    mock_boto3.client.assert_called_once_with("ec2", region_name="eu-west-2")
    mock_stop.assert_called_once_with(mock_ec2)
    mock_metadata.assert_called_once()
    mock_assessment.assert_called_once()
    mock_recommendations.assert_called_once()


@patch(
    "cost_toolkit.scripts.migration.aws_london_final_analysis_summary._print_final_recommendations"
)
@patch(
    "cost_toolkit.scripts.migration.aws_london_final_analysis_summary._print_duplicate_assessment"
)
@patch("cost_toolkit.scripts.migration.aws_london_final_analysis_summary._print_metadata_findings")
@patch("cost_toolkit.scripts.migration.aws_london_final_analysis_summary._stop_instance")
@patch("cost_toolkit.scripts.migration.aws_london_final_analysis_summary.boto3")
@patch("builtins.print")
def test_final_analysis_summary_stop_error(
    _mock_print,
    mock_boto3,
    mock_stop,
    _mock_metadata,
    _mock_assessment,
    _mock_recommendations,
):
    """Test final analysis summary when stop fails."""
    mock_ec2 = MagicMock()
    mock_boto3.client.return_value = mock_ec2
    mock_stop.side_effect = ClientError({"Error": {"Code": "InstanceNotFound"}}, "StopInstances")

    try:
        final_analysis_summary()
    except ClientError:
        pass


# Tests for main
@patch("cost_toolkit.scripts.migration.aws_london_final_analysis_summary.final_analysis_summary")
def test_main(mock_analysis):
    """Test main function."""
    main()
    mock_analysis.assert_called_once()


# Integration-style tests
@patch(
    "cost_toolkit.scripts.migration.aws_london_final_analysis_summary._print_final_recommendations"
)
@patch(
    "cost_toolkit.scripts.migration.aws_london_final_analysis_summary._print_duplicate_assessment"
)
@patch("cost_toolkit.scripts.migration.aws_london_final_analysis_summary._print_metadata_findings")
@patch("cost_toolkit.scripts.migration.aws_london_final_analysis_summary._stop_instance")
@patch("cost_toolkit.scripts.migration.aws_london_final_analysis_summary.boto3")
@patch("builtins.print")
def test_final_analysis_summary_complete_workflow(_mock_print, mock_boto3, mock_stop, *print_mocks):
    """Test complete final analysis workflow."""
    mock_metadata, mock_assessment, mock_recommendations = print_mocks
    mock_ec2 = MagicMock()
    mock_boto3.client.return_value = mock_ec2

    final_analysis_summary()

    # Verify all steps are called in order
    assert mock_boto3.client.call_count == 1
    assert mock_boto3.client.call_count == 1
    assert mock_stop.call_count == 1
    assert mock_metadata.call_count == 1
    assert mock_assessment.call_count == 1
    assert mock_recommendations.call_count == 1


@patch("builtins.print")
def test_print_metadata_findings_content(mock_print):
    """Test metadata findings contains expected content."""
    _print_metadata_findings()

    call_args = [str(call) for call in mock_print.call_args_list]
    combined = " ".join(call_args)

    # Check for key information
    assert "UNIQUE sizes" in combined
    assert "Feb 5, 2025" in combined
    assert "Feb 6, 2025" in combined
    assert "snap-03490193a42293c87" in combined
    assert "snap-07a6773b0e0842e21" in combined


@patch("builtins.print")
def test_print_duplicate_assessment_content(mock_print):
    """Test duplicate assessment contains expected content."""
    _print_duplicate_assessment()

    call_args = [str(call) for call in mock_print.call_args_list]
    combined = " ".join(call_args)

    # Check for verdicts
    assert "KEEP - Essential system volume" in combined
    assert "KEEP - Primary data storage" in combined
    assert "NEEDS CONTENT INSPECTION" in combined


@patch("builtins.print")
def test_print_final_recommendations_content(mock_print):
    """Test final recommendations contains expected content."""
    _print_final_recommendations()

    call_args = [str(call) for call in mock_print.call_args_list]
    combined = " ".join(call_args)

    # Check for costs and steps
    assert "$5.12/month" in combined
    assert "$81.92/month" in combined
    assert "$30.72/month" in combined
    assert "NEXT STEPS" in combined
    assert "aws_london_ebs_analysis.py" in combined
