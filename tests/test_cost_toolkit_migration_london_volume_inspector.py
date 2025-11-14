"""Comprehensive tests for aws_london_volume_inspector.py."""

from __future__ import annotations

from unittest.mock import patch

from cost_toolkit.scripts.migration.aws_london_volume_inspector import (
    SYSTEM_INFO_COMMANDS,
    VOLUME_INSPECTION_COMMANDS,
    _generate_inspection_script,
    _print_command_list,
    _print_cost_optimization,
    _print_duplicate_analysis,
    _print_header,
    _print_recommendations,
    _print_usage_instructions,
    _print_volume_summary,
    _script_footer,
    _script_header,
    _volume_inspect_commands,
    inspect_volumes_via_ssh,
    main,
    setup_aws_credentials,
)


def test_setup_credentials_calls_utils():
    """Test credentials setup delegates to aws_utils."""
    with patch(
        "cost_toolkit.scripts.migration.aws_london_volume_inspector.aws_utils"
    ) as mock_utils:
        setup_aws_credentials()
    mock_utils.setup_aws_credentials.assert_called_once()


def test_print_header_output(capsys):
    """Test header is printed with IP address."""
    _print_header("192.168.1.1")

    captured = capsys.readouterr()
    assert "AWS London Volume Content Inspector" in captured.out
    assert "192.168.1.1" in captured.out
    assert "Volume Analysis" in captured.out


class TestPrintCommandList:
    """Tests for _print_command_list function."""

    def test_print_command_list_numbered(self, capsys):
        """Test commands are printed with numbers."""
        commands = ["ls -la", "df -h", "mount"]

        _print_command_list("Test Commands", commands)

        captured = capsys.readouterr()
        assert "Test Commands:" in captured.out
        assert "1. ls -la" in captured.out
        assert "2. df -h" in captured.out
        assert "3. mount" in captured.out

    def test_print_command_list_empty(self, capsys):
        """Test empty command list."""
        _print_command_list("Empty", [])

        captured = capsys.readouterr()
        assert "Empty:" in captured.out


class TestScriptHeader:
    """Tests for _script_header function."""

    def test_script_header_has_shebang(self):
        """Test script header has bash shebang."""
        header = _script_header()
        assert header.startswith("#!/bin/bash")

    def test_script_header_includes_analysis_title(self):
        """Test header includes analysis title."""
        header = _script_header()
        assert "LONDON INSTANCE VOLUME ANALYSIS" in header

    def test_script_header_has_disk_commands(self):
        """Test header includes disk inspection commands."""
        header = _script_header()
        assert "df -h" in header
        assert "lsblk" in header
        assert "mount" in header
        assert "fdisk -l" in header


class TestVolumeInspectCommands:
    """Tests for _volume_inspect_commands function."""

    def test_inspect_commands_includes_device(self):
        """Test inspect commands include device path."""
        commands = _volume_inspect_commands("/dev/xvda", "Test Volume", "/tmp/test")
        assert "/dev/xvda" in commands

    def test_inspect_commands_mounts_readonly(self):
        """Test volume is mounted read-only."""
        commands = _volume_inspect_commands("/dev/xvda", "Test", "/tmp/test")
        assert "mount -o ro" in commands

    def test_inspect_commands_creates_mount_point(self):
        """Test mount point directory is created."""
        commands = _volume_inspect_commands("/dev/xvda", "Test", "/tmp/test")
        assert "mkdir -p /tmp/test" in commands

    def test_inspect_commands_lists_contents(self):
        """Test commands list directory contents."""
        commands = _volume_inspect_commands("/dev/xvda", "Test", "/tmp/test")
        assert "ls -la" in commands
        assert "du -sh" in commands

    def test_inspect_commands_unmounts_after(self):
        """Test volume is unmounted after inspection."""
        commands = _volume_inspect_commands("/dev/xvda", "Test", "/tmp/test")
        assert "umount /tmp/test" in commands

    def test_inspect_commands_checks_filesystem(self):
        """Test filesystem is checked before mounting."""
        commands = _volume_inspect_commands("/dev/xvda", "Test", "/tmp/test")
        assert "file -s /dev/xvda" in commands
        assert "grep -q filesystem" in commands


class TestScriptFooter:
    """Tests for _script_footer function."""

    def test_script_footer_has_analysis_complete(self):
        """Test footer includes completion message."""
        footer = _script_footer()
        assert "ANALYSIS COMPLETE" in footer

    def test_script_footer_has_instructions(self):
        """Test footer includes analysis instructions."""
        footer = _script_footer()
        assert "duplicates" in footer
        assert "most recent data" in footer
        assert "safely deleted" in footer


class TestGenerateInspectionScript:
    """Tests for _generate_inspection_script function."""

    def test_generate_script_combines_parts(self):
        """Test script combines header, inspections, and footer."""
        script = _generate_inspection_script()
        assert "#!/bin/bash" in script
        assert "LONDON INSTANCE VOLUME ANALYSIS" in script
        assert "ANALYSIS COMPLETE" in script

    def test_generate_script_includes_all_volumes(self):
        """Test script includes all volume inspections."""
        script = _generate_inspection_script()
        assert "/dev/xvdbo" in script  # Tars - 1024GB
        assert "/dev/sdd" in script  # 384GB
        assert "/dev/sde" in script  # Tars 2 - 1024GB
        assert "/dev/sda1" in script  # Tars 3 - 64GB

    def test_generate_script_has_unique_mount_points(self):
        """Test each volume has unique mount point."""
        script = _generate_inspection_script()
        assert "/tmp/inspect_tars" in script
        assert "/tmp/inspect_384" in script
        assert "/tmp/inspect_tars2" in script
        assert "/tmp/inspect_tars3" in script


class TestPrintUsageInstructions:
    """Tests for _print_usage_instructions function."""

    def test_print_usage_shows_scp_command(self, capsys):
        """Test usage includes scp command."""
        _print_usage_instructions("10.0.0.1")

        captured = capsys.readouterr()
        assert "scp" in captured.out
        assert "10.0.0.1" in captured.out
        assert "/tmp/volume_inspection.sh" in captured.out

    def test_print_usage_shows_ssh_command(self, capsys):
        """Test usage includes ssh command."""
        _print_usage_instructions("10.0.0.1")

        captured = capsys.readouterr()
        assert "ssh" in captured.out
        assert "10.0.0.1" in captured.out

    def test_print_usage_shows_execution(self, capsys):
        """Test usage shows how to execute script."""
        _print_usage_instructions("10.0.0.1")

        captured = capsys.readouterr()
        assert "chmod +x" in captured.out
        assert "./tmp/volume_inspection.sh" in captured.out


class TestPrintVolumeSummary:
    """Tests for _print_volume_summary function."""

    def test_print_summary_lists_volumes(self, capsys):
        """Test summary lists all volumes."""
        _print_volume_summary()

        captured = capsys.readouterr()
        assert "VOLUME SUMMARY FROM ANALYSIS" in captured.out
        assert "4 volumes attached" in captured.out
        assert "1 unattached volume" in captured.out

    def test_print_summary_shows_volume_details(self, capsys):
        """Test summary shows volume sizes and dates."""
        _print_volume_summary()

        captured = capsys.readouterr()
        assert "1024 GB" in captured.out
        assert "384 GB" in captured.out
        assert "64 GB" in captured.out
        assert "32 GB" in captured.out
        assert "2023-02-25" in captured.out
        assert "2025-02-06" in captured.out

    def test_print_summary_marks_oldest_newest(self, capsys):
        """Test summary marks oldest and newest volumes."""
        _print_volume_summary()

        captured = capsys.readouterr()
        assert "OLDEST" in captured.out
        assert "NEWEST" in captured.out


def test_print_analysis_identifies_duplicates(capsys):
    """Test duplicate analysis identifies duplicate volumes."""
    _print_duplicate_analysis()

    captured = capsys.readouterr()
    assert "DUPLICATE ANALYSIS" in captured.out
    assert "Two 1024 GB volumes" in captured.out
    assert "Tars" in captured.out
    assert "Tars 2" in captured.out


def test_print_optimization_shows_savings(capsys):
    """Test cost optimization shows potential savings."""
    _print_cost_optimization()

    captured = capsys.readouterr()
    assert "COST OPTIMIZATION POTENTIAL" in captured.out
    assert "1024 GB" in captured.out
    assert "~$82/month" in captured.out
    assert "32 GB" in captured.out
    assert "~$3/month" in captured.out
    assert "~$85/month" in captured.out


class TestPrintRecommendations:
    """Tests for _print_recommendations function."""

    def test_print_recommendations_shows_steps(self, capsys):
        """Test recommendations show action steps."""
        _print_recommendations()

        captured = capsys.readouterr()
        assert "RECOMMENDATION" in captured.out
        assert "Inspect" in captured.out
        assert "delete" in captured.out

    def test_print_recommendations_lists_volumes_to_keep(self, capsys):
        """Test recommendations list volumes to keep."""
        _print_recommendations()

        captured = capsys.readouterr()
        assert "Tars 2" in captured.out
        assert "384" in captured.out
        assert "Tars 3" in captured.out


class TestInspectVolumesViaSsh:
    """Tests for inspect_volumes_via_ssh function."""

    def test_inspect_creates_script_file(self, capsys):
        """Test inspection creates script file."""
        with patch(
            "cost_toolkit.scripts.migration.aws_london_volume_inspector.setup_aws_credentials"
        ):
            with patch("builtins.open", create=True) as mock_open:
                inspect_volumes_via_ssh()

        mock_open.assert_called_once_with("/tmp/volume_inspection.sh", "w", encoding="utf-8")
        captured = capsys.readouterr()
        assert "AWS London Volume Content Inspector" in captured.out

    def test_inspect_prints_all_sections(self, capsys):
        """Test all information sections are printed."""
        with patch(
            "cost_toolkit.scripts.migration.aws_london_volume_inspector.setup_aws_credentials"
        ):
            with patch("builtins.open", create=True):
                inspect_volumes_via_ssh()

        captured = capsys.readouterr()
        assert "System Information Commands" in captured.out
        assert "Volume Inspection Commands" in captured.out
        assert "VOLUME SUMMARY" in captured.out
        assert "DUPLICATE ANALYSIS" in captured.out
        assert "COST OPTIMIZATION" in captured.out
        assert "RECOMMENDATION" in captured.out

    def test_inspect_uses_correct_ip(self, capsys):
        """Test correct instance IP is used."""
        with patch(
            "cost_toolkit.scripts.migration.aws_london_volume_inspector.setup_aws_credentials"
        ):
            with patch("builtins.open", create=True):
                inspect_volumes_via_ssh()

        captured = capsys.readouterr()
        assert "35.179.157.191" in captured.out


def test_main_calls_inspect_volumes_via_ssh():
    """Test main function calls inspect_volumes_via_ssh."""
    with patch(
        "cost_toolkit.scripts.migration.aws_london_volume_inspector.inspect_volumes_via_ssh"
    ) as mock_inspect:
        main()
    mock_inspect.assert_called_once()


def test_system_info_commands_constant():
    """Test SYSTEM_INFO_COMMANDS constant is defined."""
    assert isinstance(SYSTEM_INFO_COMMANDS, list)
    assert len(SYSTEM_INFO_COMMANDS) > 0
    assert "df -h" in SYSTEM_INFO_COMMANDS
    assert "lsblk" in SYSTEM_INFO_COMMANDS


def test_volume_inspection_commands_constant():
    """Test VOLUME_INSPECTION_COMMANDS constant is defined."""
    assert isinstance(VOLUME_INSPECTION_COMMANDS, list)
    assert len(VOLUME_INSPECTION_COMMANDS) > 0
    assert any("xvdbo" in cmd for cmd in VOLUME_INSPECTION_COMMANDS)
