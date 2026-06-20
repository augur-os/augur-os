import yaml

from src.config import preferences


def test_preferences_path_uses_runtime_dir(tmp_path, monkeypatch):
    runtime_dir = tmp_path / "runtime"
    monkeypatch.setattr(preferences, "get_runtime_dir", lambda: runtime_dir)

    assert preferences.get_preferences_path() == runtime_dir / "preferences.yaml"


def test_load_preferences_migrates_legacy_repo_file(tmp_path, monkeypatch):
    runtime_path = tmp_path / "state" / "preferences.yaml"
    legacy_path = tmp_path / "repo" / "config" / "preferences.yaml"
    legacy_path.parent.mkdir(parents=True)
    legacy_path.write_text(
        yaml.safe_dump(
            {
                "airplane_mode": {"enabled": True},
                "local_backends": {"ollama": {"model": "llama3.2:3b"}},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(preferences, "get_preferences_path", lambda: runtime_path)
    monkeypatch.setattr(
        preferences,
        "get_legacy_preferences_paths",
        lambda: [legacy_path],
    )

    data = preferences.load_preferences()

    assert data["airplane_mode"]["enabled"] is True
    assert data["local_backends"]["ollama"]["model"] == "llama3.2:3b"
    assert yaml.safe_load(runtime_path.read_text(encoding="utf-8")) == data


def test_save_preferences_writes_runtime_file(tmp_path, monkeypatch):
    runtime_path = tmp_path / "state" / "preferences.yaml"
    monkeypatch.setattr(preferences, "get_preferences_path", lambda: runtime_path)

    preferences.save_preferences({"ui_mode": "light"})

    assert yaml.safe_load(runtime_path.read_text(encoding="utf-8")) == {"ui_mode": "light"}
