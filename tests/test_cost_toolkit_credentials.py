from __future__ import annotations

import importlib
import os

import pytest

from cost_toolkit.scripts import aws_utils


def test_load_aws_credentials_respects_custom_env(tmp_path, monkeypatch):
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


@pytest.mark.parametrize(
    "module_path",
    [
        "cost_toolkit.scripts.cleanup.aws_cleanup_script",
        "cost_toolkit.scripts.cleanup.aws_cloudwatch_cleanup",
        "cost_toolkit.scripts.migration.aws_start_and_migrate",
    ],
)
def test_script_setup_delegates_to_shared_helper(module_path, monkeypatch):
    module = importlib.import_module(module_path)

    called = {"count": 0}

    def fake_setup(_env_path=None):
        called["count"] += 1

    monkeypatch.setattr("cost_toolkit.scripts.aws_utils.setup_aws_credentials", fake_setup)

    setup_fn = getattr(module, "setup_aws_credentials")
    setup_fn()

    assert called["count"] == 1
