from io import StringIO
from unittest import mock

import migration_utils


class TestFormatSize:
    """Tests for format_size function"""

    def test_format_size_zero_bytes(self):
        """Test formatting 0 bytes"""
        assert migration_utils.format_size(0) == "0.00 B"

    def test_format_size_single_byte(self):
        """Test formatting 1 byte"""
        assert migration_utils.format_size(1) == "1.00 B"

    def test_format_size_small_bytes(self):
        """Test formatting small number of bytes"""
        assert migration_utils.format_size(512) == "512.00 B"

    def test_format_size_exact_1024_bytes(self):
        """Test formatting exactly 1024 bytes (boundary between B and KB)"""
        assert migration_utils.format_size(1024) == "1.00 KB"

    def test_format_size_kilobytes(self):
        """Test formatting kilobytes"""
        assert migration_utils.format_size(2048) == "2.00 KB"
        assert migration_utils.format_size(5120) == "5.00 KB"

    def test_format_size_kilobytes_fractional(self):
        """Test formatting fractional kilobytes"""
        assert migration_utils.format_size(1536) == "1.50 KB"
        assert migration_utils.format_size(1843) == "1.80 KB"

    def test_format_size_exact_1mb(self):
        """Test formatting exactly 1 MB"""
        assert migration_utils.format_size(1024 * 1024) == "1.00 MB"

    def test_format_size_megabytes(self):
        """Test formatting megabytes"""
        assert migration_utils.format_size(5 * 1024 * 1024) == "5.00 MB"
        assert migration_utils.format_size(512 * 1024 * 1024) == "512.00 MB"

    def test_format_size_megabytes_fractional(self):
        """Test formatting fractional megabytes"""
        assert migration_utils.format_size(1536 * 1024) == "1.50 MB"

    def test_format_size_exact_1gb(self):
        """Test formatting exactly 1 GB"""
        assert migration_utils.format_size(1024 * 1024 * 1024) == "1.00 GB"

    def test_format_size_gigabytes(self):
        """Test formatting gigabytes"""
        assert migration_utils.format_size(2 * 1024 * 1024 * 1024) == "2.00 GB"
        assert migration_utils.format_size(512 * 1024 * 1024 * 1024) == "512.00 GB"

    def test_format_size_gigabytes_fractional(self):
        """Test formatting fractional gigabytes"""
        assert migration_utils.format_size(1536 * 1024 * 1024) == "1.50 GB"

    def test_format_size_exact_1tb(self):
        """Test formatting exactly 1 TB"""
        assert migration_utils.format_size(1024 * 1024 * 1024 * 1024) == "1.00 TB"

    def test_format_size_terabytes(self):
        """Test formatting terabytes"""
        assert migration_utils.format_size(5 * 1024 * 1024 * 1024 * 1024) == "5.00 TB"
        assert migration_utils.format_size(100 * 1024 * 1024 * 1024 * 1024) == "100.00 TB"

    def test_format_size_terabytes_fractional(self):
        """Test formatting fractional terabytes"""
        assert migration_utils.format_size(1536 * 1024 * 1024 * 1024) == "1.50 TB"

    def test_format_size_petabytes(self):
        """Test formatting petabytes (PB)"""
        assert migration_utils.format_size(1024 * 1024 * 1024 * 1024 * 1024) == "1.00 PB"
        assert migration_utils.format_size(5 * 1024 * 1024 * 1024 * 1024 * 1024) == "5.00 PB"

    def test_format_size_petabytes_fractional(self):
        """Test formatting fractional petabytes"""
        assert migration_utils.format_size(1536 * 1024 * 1024 * 1024 * 1024) == "1.50 PB"

    def test_format_size_very_large_values(self):
        """Test formatting very large values beyond PB"""
        # Even exabytes should be formatted as PB (no more units defined)
        huge_value = 1000 * 1024 * 1024 * 1024 * 1024 * 1024
        result = migration_utils.format_size(huge_value)
        assert "PB" in result

    def test_format_size_boundary_kb_to_mb(self):
        """Test boundary between KB and MB"""
        # Just below 1 MB
        assert "KB" in migration_utils.format_size(1023 * 1024)
        # Just at 1 MB
        assert migration_utils.format_size(1024 * 1024) == "1.00 MB"

    def test_format_size_boundary_mb_to_gb(self):
        """Test boundary between MB and GB"""
        # Just below 1 GB
        assert "MB" in migration_utils.format_size(1023 * 1024 * 1024)
        # Just at 1 GB
        assert migration_utils.format_size(1024 * 1024 * 1024) == "1.00 GB"

    def test_format_size_boundary_gb_to_tb(self):
        """Test boundary between GB and TB"""
        # Just below 1 TB
        assert "GB" in migration_utils.format_size(1023 * 1024 * 1024 * 1024)
        # Just at 1 TB
        assert migration_utils.format_size(1024 * 1024 * 1024 * 1024) == "1.00 TB"

    def test_format_size_boundary_tb_to_pb(self):
        """Test boundary between TB and PB"""
        # Just below 1 PB
        assert "TB" in migration_utils.format_size(1023 * 1024 * 1024 * 1024 * 1024)
        # Just at 1 PB
        assert migration_utils.format_size(1024 * 1024 * 1024 * 1024 * 1024) == "1.00 PB"


class TestFormatDuration:
    """Tests for format_duration function"""

    def test_format_duration_zero_seconds(self):
        """Test formatting 0 seconds"""
        assert migration_utils.format_duration(0) == "0s"

    def test_format_duration_single_second(self):
        """Test formatting 1 second"""
        assert migration_utils.format_duration(1) == "1s"

    def test_format_duration_multiple_seconds(self):
        """Test formatting multiple seconds"""
        assert migration_utils.format_duration(30) == "30s"
        assert migration_utils.format_duration(59) == "59s"

    def test_format_duration_exact_60_seconds(self):
        """Test formatting exactly 60 seconds (boundary between seconds and minutes)"""
        assert migration_utils.format_duration(60) == "1m 0s"

    def test_format_duration_one_minute(self):
        """Test formatting 1 minute"""
        assert migration_utils.format_duration(60) == "1m 0s"

    def test_format_duration_minutes_and_seconds(self):
        """Test formatting minutes with seconds"""
        assert migration_utils.format_duration(90) == "1m 30s"
        assert migration_utils.format_duration(125) == "2m 5s"
        assert migration_utils.format_duration(3599) == "59m 59s"

    def test_format_duration_exact_one_hour(self):
        """Test formatting exactly one hour"""
        assert migration_utils.format_duration(3600) == "1h 0m"

    def test_format_duration_hours_and_minutes(self):
        """Test formatting hours with minutes"""
        assert migration_utils.format_duration(3660) == "1h 1m"
        assert migration_utils.format_duration(5400) == "1h 30m"
        assert migration_utils.format_duration(7200) == "2h 0m"
        assert migration_utils.format_duration(9000) == "2h 30m"

    def test_format_duration_multiple_hours(self):
        """Test formatting multiple hours"""
        assert migration_utils.format_duration(10800) == "3h 0m"
        assert migration_utils.format_duration(36000) == "10h 0m"
        assert migration_utils.format_duration(82800) == "23h 0m"

    def test_format_duration_hours_with_various_minutes(self):
        """Test formatting hours with various minute values"""
        assert migration_utils.format_duration(3720) == "1h 2m"
        assert migration_utils.format_duration(7380) == "2h 3m"
        assert migration_utils.format_duration(12600) == "3h 30m"

    def test_format_duration_exact_one_day(self):
        """Test formatting exactly one day"""
        assert migration_utils.format_duration(86400) == "1d 0h"

    def test_format_duration_days_and_hours(self):
        """Test formatting days with hours"""
        assert migration_utils.format_duration(90000) == "1d 1h"
        assert migration_utils.format_duration(93600) == "1d 2h"
        assert migration_utils.format_duration(172800) == "2d 0h"

    def test_format_duration_multiple_days(self):
        """Test formatting multiple days"""
        assert migration_utils.format_duration(259200) == "3d 0h"
        assert migration_utils.format_duration(604800) == "7d 0h"
        assert migration_utils.format_duration(864000) == "10d 0h"

    def test_format_duration_days_with_various_hours(self):
        """Test formatting days with various hour values"""
        assert migration_utils.format_duration(86400 + 3600) == "1d 1h"
        assert migration_utils.format_duration(86400 * 2 + 7200) == "2d 2h"
        assert migration_utils.format_duration(86400 * 5 + 43200) == "5d 12h"

    def test_format_duration_boundary_minute_to_hour(self):
        """Test boundary between minutes and hours"""
        # Just below 1 hour
        assert migration_utils.format_duration(3599) == "59m 59s"
        # Just at 1 hour
        assert migration_utils.format_duration(3600) == "1h 0m"

    def test_format_duration_boundary_hour_to_day(self):
        """Test boundary between hours and days"""
        # Just below 1 day
        assert migration_utils.format_duration(86399) == "23h 59m"
        # Just at 1 day
        assert migration_utils.format_duration(86400) == "1d 0h"

    def test_format_duration_fractional_seconds(self):
        """Test formatting fractional seconds (should truncate)"""
        assert migration_utils.format_duration(59.9) == "59s"
        assert migration_utils.format_duration(0.5) == "0s"
        assert migration_utils.format_duration(1.9) == "1s"

    def test_format_duration_fractional_minutes(self):
        """Test formatting fractional minutes and seconds"""
        assert migration_utils.format_duration(125.9) == "2m 5s"
        assert migration_utils.format_duration(90.5) == "1m 30s"

    def test_format_duration_large_values(self):
        """Test formatting very large durations"""
        # 30 days
        assert migration_utils.format_duration(30 * 86400) == "30d 0h"
        # 100 days
        assert migration_utils.format_duration(100 * 86400) == "100d 0h"
        # 1000 days
        assert migration_utils.format_duration(1000 * 86400) == "1000d 0h"


class TestPrintVerificationSuccessMessages:
    """Tests for print_verification_success_messages function"""

    def test_print_verification_success_messages_output(self):
        """Test that the function prints expected messages"""
        captured_output = StringIO()
        with mock.patch("sys.stdout", captured_output):
            migration_utils.print_verification_success_messages()

        output = captured_output.getvalue()

        # Check that all expected lines are present
        assert "✓ All file sizes verified (exact byte match)" in output
        assert "✓ All files verified healthy and readable:" in output
        assert "Single-part files: MD5 hash (matches S3 ETag)" in output
        assert "Multipart files: SHA256 hash (verifies file integrity)" in output
        assert "Every byte of every file was read and hashed" in output

    def test_print_verification_success_messages_line_count(self):
        """Test that the function prints exactly 5 lines"""
        captured_output = StringIO()
        with mock.patch("sys.stdout", captured_output):
            migration_utils.print_verification_success_messages()

        output = captured_output.getvalue()
        lines = output.strip().split("\n")
        assert len(lines) == 5

    def test_print_verification_success_messages_indentation(self):
        """Test that messages have correct indentation"""
        captured_output = StringIO()
        with mock.patch("sys.stdout", captured_output):
            migration_utils.print_verification_success_messages()

        output = captured_output.getvalue()
        lines = output.rstrip("\n").split("\n")

        # First two lines should start with exactly two spaces
        assert lines[0].startswith("  ✓")
        assert lines[1].startswith("  ✓")

        # Lines 3-5 should have deeper indentation (4 spaces for sub-items)
        assert lines[2].startswith("    -")
        assert lines[3].startswith("    -")
        assert lines[4].startswith("    -")

    def test_print_verification_success_messages_checkmarks(self):
        """Test that all top-level messages have checkmarks"""
        captured_output = StringIO()
        with mock.patch("sys.stdout", captured_output):
            migration_utils.print_verification_success_messages()

        output = captured_output.getvalue()
        lines = output.strip().split("\n")

        # First two lines should have checkmarks
        assert "✓" in lines[0]
        assert "✓" in lines[1]

    def test_print_verification_success_messages_all_details_present(self):
        """Test that all verification details are present"""
        captured_output = StringIO()
        with mock.patch("sys.stdout", captured_output):
            migration_utils.print_verification_success_messages()

        output = captured_output.getvalue()

        # Check for specific technical details
        assert "MD5 hash" in output
        assert "SHA256 hash" in output
        assert "S3 ETag" in output
        assert "file integrity" in output
        assert "byte" in output.lower()

    def test_print_verification_success_messages_called_multiple_times(self):
        """Test that function can be called multiple times without issues"""
        captured_output = StringIO()

        # Call the function twice
        with mock.patch("sys.stdout", captured_output):
            migration_utils.print_verification_success_messages()
            migration_utils.print_verification_success_messages()

        output = captured_output.getvalue()

        # Should have two complete sets of output (10 lines total)
        lines = output.strip().split("\n")
        assert len(lines) == 10

    def test_print_verification_success_messages_no_return_value(self):
        """Test that function returns None"""
        result = migration_utils.print_verification_success_messages()
        assert result is None
