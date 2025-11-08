"""Tests for cost_toolkit AWS credentials loading."""

from __future__ import annotations

import os

from cost_toolkit.scripts import aws_utils


def test_load_aws_credentials_respects_custom_env(tmp_path, monkeypatch):
    """Test load_aws_credentials loads from custom AWS_ENV_FILE."""
    env_file = tmp_path / "aws.env"
    env_file.write_text(
        "\n".join(
            [
                "AWS_ACCESS_KEY_ID=TESTKEY",
                "AWS_SECRET_ACCESS_KEY=TESTSECRET",
                "AWS_DEFAULT_REGION=us-east-1",
            ]
        ),
        encoding="utf-8",
    )

    # Ensure the values are pulled from the temporary env file
    monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)
    monkeypatch.delenv("AWS_DEFAULT_REGION", raising=False)
    monkeypatch.setenv("AWS_ENV_FILE", str(env_file))

    assert aws_utils.load_aws_credentials()
    assert os.environ["AWS_ACCESS_KEY_ID"] == "TESTKEY"
    assert os.environ["AWS_SECRET_ACCESS_KEY"] == "TESTSECRET"
    assert os.environ["AWS_DEFAULT_REGION"] == "us-east-1"


def test_load_aws_credentials_warns_for_missing_file(monkeypatch, capsys):
    """Test load_aws_credentials warns when credential file is missing."""
    monkeypatch.delenv("AWS_ENV_FILE", raising=False)
    monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)
    env_file = os.path.join(os.getcwd(), "nonexistent.env")
    monkeypatch.setenv("AWS_ENV_FILE", env_file)

    assert not aws_utils.load_aws_credentials()
    captured = capsys.readouterr()
    assert "AWS credentials not found" in captured.out
