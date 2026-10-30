import os
from pathlib import Path


def test_project_env_overrides_stale_process_key(tmp_path: Path, monkeypatch):
    from backend.config import load_project_env

    env_file = tmp_path / ".env"
    env_file.write_text("DEEPSEEK_API_KEY=fresh-local-key\n", encoding="utf-8")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "stale-process-key")

    assert load_project_env(env_file) is True
    assert os.environ["DEEPSEEK_API_KEY"] == "fresh-local-key"


def test_empty_project_env_does_not_erase_existing_key(tmp_path: Path, monkeypatch):
    from backend.config import load_project_env

    env_file = tmp_path / ".env"
    env_file.write_text("DEEPSEEK_API_KEY=\n", encoding="utf-8")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "existing-key")

    assert load_project_env(env_file) is False
    assert os.environ["DEEPSEEK_API_KEY"] == "existing-key"
