"""Tests for cost_toolkit/scripts/optimization/snapshot_export_fixed/monitoring.py module."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from cost_toolkit.scripts.optimization.snapshot_export_fixed import constants
from cost_toolkit.scripts.optimization.snapshot_export_fixed.constants import (
    S3FileValidationException,
)
from cost_toolkit.scripts.optimization.snapshot_export_fixed.monitoring import (
    calculate_cost_savings,
    check_s3_file_completion,
    verify_s3_export_final,
)


@pytest.fixture(name="s3")
def fixture_s3():
    """Create a mock S3 client."""
    client = MagicMock()
    client.exceptions.NoSuchKey = type("NoSuchKey", (Exception,), {})
    return client


def test_calculate_cost_savings_basic():
    """Test calculate_cost_savings with basic snapshot size."""
    result = calculate_cost_savings(100)

    assert result["ebs_cost"] == 5.0  # 100 * 0.05
    assert result["s3_cost"] == 2.3  # 100 * 0.023
    assert result["monthly_savings"] == 2.7  # 5.0 - 2.3
    assert abs(result["annual_savings"] - 32.4) < 0.001  # 2.7 * 12, handle floating point
    assert result["savings_percentage"] == 54.0  # (2.7 / 5.0) * 100


def test_calculate_cost_savings_zero():
    """Test calculate_cost_savings with zero size handles division by zero."""
    # The function will divide by zero for savings_percentage
    # We should test that it raises ZeroDivisionError or handle it
    with pytest.raises(ZeroDivisionError):
        calculate_cost_savings(0)


def test_calculate_cost_savings_large_snapshot():
    """Test calculate_cost_savings with large snapshot."""
    result = calculate_cost_savings(1000)

    assert result["ebs_cost"] == 50.0
    assert result["s3_cost"] == 23.0
    assert result["monthly_savings"] == 27.0
    assert result["annual_savings"] == 324.0


def test_calculate_cost_savings_fractional():
    """Test calculate_cost_savings with fractional GB."""
    result = calculate_cost_savings(10.5)

    assert abs(result["ebs_cost"] - 0.525) < 0.001
    assert abs(result["s3_cost"] - 0.2415) < 0.001
    assert abs(result["monthly_savings"] - 0.2835) < 0.001


def test_verify_s3_export_final_success(s3, capsys):
    """Test verify_s3_export_final with successful verification."""
    s3.head_object.return_value = {
        "ContentLength": 107374182400,  # 100 GB
        "LastModified": datetime(2024, 1, 1, 12, 0, 0),
    }

    result = verify_s3_export_final(s3, "test-bucket", "test-key.vmdk", 100)

    assert result["size_bytes"] == 107374182400
    assert abs(result["size_gb"] - 100.0) < 0.1
    assert result["last_modified"] == datetime(2024, 1, 1, 12, 0, 0)

    s3.head_object.assert_called_once_with(Bucket="test-bucket", Key="test-key.vmdk")

    captured = capsys.readouterr()
    assert "Final verification" in captured.out
    assert "File exists in S3!" in captured.out
    assert "Size validation passed" in captured.out


def test_verify_s3_export_final_size_too_small(s3):
    """Test verify_s3_export_final fails when file is too small."""
    # File is 1 GB but expected is 100 GB (too small even with compression)
    s3.head_object.return_value = {
        "ContentLength": 1073741824,  # 1 GB
        "LastModified": datetime(2024, 1, 1, 12, 0, 0),
    }

    with pytest.raises(S3FileValidationException, match="Final size validation failed"):
        verify_s3_export_final(s3, "test-bucket", "test-key.vmdk", 100)


def test_verify_s3_export_final_size_too_large(s3):
    """Test verify_s3_export_final fails when file is too large."""
    # File is 200 GB but expected is 100 GB (exceeds max expansion ratio)
    s3.head_object.return_value = {
        "ContentLength": 214748364800,  # 200 GB
        "LastModified": datetime(2024, 1, 1, 12, 0, 0),
    }

    with pytest.raises(S3FileValidationException, match="Final size validation failed"):
        verify_s3_export_final(s3, "test-bucket", "test-key.vmdk", 100)


def test_verify_s3_export_final_within_compression_range(s3):
    """Test verify_s3_export_final accepts highly compressed files."""
    # File is 15 GB for 100 GB snapshot (15% of original = valid compression)
    s3.head_object.return_value = {
        "ContentLength": 16106127360,  # 15 GB
        "LastModified": datetime(2024, 1, 1, 12, 0, 0),
    }

    result = verify_s3_export_final(s3, "test-bucket", "test-key.vmdk", 100)

    assert result["size_bytes"] == 16106127360


def test_verify_s3_export_final_within_expansion_range(s3):
    """Test verify_s3_export_final accepts slightly expanded files."""
    # File is 110 GB for 100 GB snapshot (110% = valid expansion)
    s3.head_object.return_value = {
        "ContentLength": 118111600640,  # 110 GB
        "LastModified": datetime(2024, 1, 1, 12, 0, 0),
    }

    result = verify_s3_export_final(s3, "test-bucket", "test-key.vmdk", 100)

    assert result["size_bytes"] == 118111600640


def test_check_s3_file_completion_success_fast_check(s3, capsys):
    """Test check_s3_file_completion with fast_check mode."""
    s3.head_object.return_value = {
        "ContentLength": 107374182400,  # 100 GB
        "LastModified": datetime(2024, 1, 1, 12, 0, 0),
    }

    with patch(
        "cost_toolkit.scripts.optimization.snapshot_export_fixed.monitoring._WAIT_EVENT.wait"
    ):
        result = check_s3_file_completion(s3, "test-bucket", "test-key.vmdk", 100, fast_check=True)

    # Fast check requires 2 stable checks (2 minutes / 1 minute interval)
    assert result["stability_checks"] == 2
    assert abs(result["size_gb"] - 100.0) < 0.1

    captured = capsys.readouterr()
    assert "Checking S3 file stability" in captured.out
    assert "File size stable" in captured.out


def test_check_s3_file_completion_success_normal_check(s3):
    """Test check_s3_file_completion with normal stability check."""
    s3.head_object.return_value = {
        "ContentLength": 107374182400,  # 100 GB
        "LastModified": datetime(2024, 1, 1, 12, 0, 0),
    }

    with patch(
        "cost_toolkit.scripts.optimization.snapshot_export_fixed.monitoring._WAIT_EVENT.wait"
    ):
        result = check_s3_file_completion(s3, "test-bucket", "test-key.vmdk", 100, fast_check=False)

    # Normal check requires 2 stable checks (10 minutes / 5 minute interval)
    assert result["stability_checks"] == 2
    assert abs(result["size_gb"] - 100.0) < 0.1


def test_check_s3_file_completion_file_growing(s3, capsys):
    """Test check_s3_file_completion when file is still growing then fails."""
    # The loop runs exactly 2 times (fast_check=True)
    # If file size changes on check 2, it resets but we've already done 2 iterations
    # So the function will fail with only 1 stable check
    sizes = [
        53687091200,  # 50 GB - check 1
        75161927680,  # 70 GB - check 2 (different, resets to 1 check)
    ]

    call_count = [0]

    def mock_head_object(*_args, **_kwargs):
        size = sizes[call_count[0]]
        call_count[0] += 1
        return {"ContentLength": size, "LastModified": datetime(2024, 1, 1, 12, 0, 0)}

    s3.head_object.side_effect = mock_head_object

    with patch(
        "cost_toolkit.scripts.optimization.snapshot_export_fixed.monitoring._WAIT_EVENT.wait"
    ):
        # Should fail because file is still growing
        with pytest.raises(S3FileValidationException, match="File not stable"):
            check_s3_file_completion(s3, "test-bucket", "test-key.vmdk", 100, fast_check=True)

    captured = capsys.readouterr()
    assert "File size changed" in captured.out
    assert "File still growing" in captured.out


def test_check_s3_file_completion_file_not_found_first_check(s3, capsys):
    """Test check_s3_file_completion when file not found on first check fails."""
    # The loop runs exactly 2 times (fast_check=True)
    # If first check fails, _handle_file_not_found returns empty list
    # Then check 2 finds the file but only has 1 check - should fail
    call_count = [0]

    def mock_head_object(*_args, **_kwargs):
        if call_count[0] == 0:
            call_count[0] += 1
            raise s3.exceptions.NoSuchKey()
        # Second check finds the file
        call_count[0] += 1
        return {"ContentLength": 107374182400, "LastModified": datetime(2024, 1, 1, 12, 0, 0)}

    s3.head_object.side_effect = mock_head_object

    with patch(
        "cost_toolkit.scripts.optimization.snapshot_export_fixed.monitoring._WAIT_EVENT.wait"
    ):
        # Should fail because only 1 successful check out of 2 required
        with pytest.raises(S3FileValidationException, match="File not stable"):
            check_s3_file_completion(s3, "test-bucket", "test-key.vmdk", 100, fast_check=True)

    captured = capsys.readouterr()
    assert "S3 file not found yet - this is normal during export" in captured.out


def test_check_s3_file_completion_file_disappeared(s3):
    """Test check_s3_file_completion when file disappears during checks."""
    # First check succeeds, second check file disappears
    call_count = [0]

    def mock_head_object(*_args, **_kwargs):
        if call_count[0] == 0:
            call_count[0] += 1
            return {"ContentLength": 107374182400, "LastModified": datetime(2024, 1, 1, 12, 0, 0)}
        raise s3.exceptions.NoSuchKey()

    s3.head_object.side_effect = mock_head_object

    with patch(
        "cost_toolkit.scripts.optimization.snapshot_export_fixed.monitoring._WAIT_EVENT.wait"
    ):
        with pytest.raises(S3FileValidationException, match="S3 file disappeared"):
            check_s3_file_completion(s3, "test-bucket", "test-key.vmdk", 100, fast_check=True)


def test_check_s3_file_completion_api_error(s3):
    """Test check_s3_file_completion handles API errors."""
    s3.head_object.side_effect = ClientError({"Error": {"Code": "ServiceError"}}, "HeadObject")

    with patch(
        "cost_toolkit.scripts.optimization.snapshot_export_fixed.monitoring._WAIT_EVENT.wait"
    ):
        with pytest.raises(S3FileValidationException, match="Failed to check S3 file"):
            check_s3_file_completion(s3, "test-bucket", "test-key.vmdk", 100, fast_check=True)


def test_check_s3_file_completion_insufficient_stable_checks(s3):
    """Test check_s3_file_completion when file doesn't stabilize."""
    # File keeps growing, never stabilizes
    call_count = [0]

    def mock_head_object(*_args, **_kwargs):
        # Each check returns a different size
        size = 53687091200 + (call_count[0] * 10737418240)  # Starts at 50 GB, adds 10 GB each time
        call_count[0] += 1
        return {"ContentLength": size, "LastModified": datetime(2024, 1, 1, 12, 0, 0)}

    s3.head_object.side_effect = mock_head_object

    with patch(
        "cost_toolkit.scripts.optimization.snapshot_export_fixed.monitoring._WAIT_EVENT.wait"
    ):
        with pytest.raises(S3FileValidationException, match="File not stable"):
            check_s3_file_completion(s3, "test-bucket", "test-key.vmdk", 100, fast_check=True)


def test_check_s3_file_completion_size_variance_warning(s3, capsys):
    """Test check_s3_file_completion warns about size variance."""
    # File is 50 GB but expected 100 GB (50% variance, but within valid compression range)
    # The function only shows variance warning at the end via _validate_final_size
    s3.head_object.return_value = {
        "ContentLength": 53687091200,  # 50 GB
        "LastModified": datetime(2024, 1, 1, 12, 0, 0),
    }

    with patch(
        "cost_toolkit.scripts.optimization.snapshot_export_fixed.monitoring._WAIT_EVENT.wait"
    ):
        result = check_s3_file_completion(s3, "test-bucket", "test-key.vmdk", 100, fast_check=True)

    # Should succeed since 50 GB is within the valid compression range
    assert result["stability_checks"] == 2
    assert abs(result["size_gb"] - 50.0) < 0.1

    captured = capsys.readouterr()
    # The function will show variance warning since 50 GB != 100 GB
    assert "Size variance" in captured.out or "50.00 GB" in captured.out


def test_check_s3_file_completion_uses_correct_config():
    """Test check_s3_file_completion uses correct timing configuration."""
    # Test fast check config
    # pylint: disable=import-outside-toplevel
    from cost_toolkit.scripts.optimization.snapshot_export_fixed.monitoring import (
        _get_stability_config,
    )

    fast_config = _get_stability_config(fast_check=True)
    assert fast_config["stability_required_minutes"] == constants.S3_FAST_CHECK_MINUTES
    assert fast_config["check_interval_minutes"] == constants.S3_FAST_CHECK_INTERVAL_MINUTES

    # Test normal check config
    normal_config = _get_stability_config(fast_check=False)
    assert normal_config["stability_required_minutes"] == constants.S3_STABILITY_CHECK_MINUTES
    assert normal_config["check_interval_minutes"] == constants.S3_STABILITY_CHECK_INTERVAL_MINUTES


def test_check_s3_file_completion_waits_between_checks(s3):
    """Test check_s3_file_completion waits between stability checks."""
    s3.head_object.return_value = {
        "ContentLength": 107374182400,
        "LastModified": datetime(2024, 1, 1, 12, 0, 0),
    }

    with patch(
        "cost_toolkit.scripts.optimization.snapshot_export_fixed.monitoring._WAIT_EVENT.wait"
    ) as mock_sleep:
        check_s3_file_completion(s3, "test-bucket", "test-key.vmdk", 100, fast_check=True)

        # Should sleep once (between first and second check)
        assert mock_sleep.call_count == 1
        # Fast check interval is 1 minute = 60 seconds
        mock_sleep.assert_called_with(constants.S3_FAST_CHECK_INTERVAL_MINUTES * 60)


def test_verify_s3_export_final_prints_file_info(s3, capsys):
    """Test verify_s3_export_final prints detailed file information."""
    test_date = datetime(2024, 1, 1, 12, 30, 45)
    s3.head_object.return_value = {
        "ContentLength": 107374182400,
        "LastModified": test_date,
    }

    verify_s3_export_final(s3, "my-bucket", "my-key.vmdk", 100)

    captured = capsys.readouterr()
    assert "s3://my-bucket/my-key.vmdk" in captured.out
    assert "100.00 GB" in captured.out
    assert "107,374,182,400 bytes" in captured.out


def test_calculate_cost_savings_returns_all_fields():
    """Test calculate_cost_savings returns all expected fields."""
    result = calculate_cost_savings(50)

    assert "ebs_cost" in result
    assert "s3_cost" in result
    assert "monthly_savings" in result
    assert "annual_savings" in result
    assert "savings_percentage" in result
    assert len(result) == 5
