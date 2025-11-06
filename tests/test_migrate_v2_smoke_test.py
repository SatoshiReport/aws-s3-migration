"""Tests for the migrate_v2 smoke test helper."""

import migrate_v2


def test_run_smoke_test_simulates_full_flow(monkeypatch, tmp_path, capsys):
    """Smoke test creates data, runs migrator, and cleans external drive."""

    external_drive = tmp_path / "external_drive"
    monkeypatch.setattr(migrate_v2.config, "LOCAL_BASE_PATH", str(external_drive))
    monkeypatch.setenv("MIGRATE_V2_SMOKE_FAKE_S3", "1")
    original_state_path = migrate_v2.config.STATE_DB_PATH

    migrate_v2.run_smoke_test()

    captured = capsys.readouterr().out
    assert "Step 1/3: Creating sample files in simulated S3..." in captured
    assert "Step 2/3: Running full migrate_v2 workflow..." in captured
    assert "Step 3/3: Removing local files moved for the smoke test..." in captured
    assert "Flow             : create files -> run prod script -> delete local data" in captured
    assert not list(external_drive.glob("smoke-test-*"))
    assert migrate_v2.config.STATE_DB_PATH == original_state_path
