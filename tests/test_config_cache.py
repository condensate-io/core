import json
import time

import pytest

import src.config_cache as config_cache
from src.config_cache import invalidate_json_config, load_json_config


@pytest.fixture(autouse=True)
def clear_config_cache():
    with config_cache._lock:
        config_cache._cache.clear()
    yield
    with config_cache._lock:
        config_cache._cache.clear()


def test_load_json_config_caches_until_ttl_expires(tmp_path, monkeypatch):
    config_file = tmp_path / "test_config.json"
    config_file.write_text(json.dumps({"version": 1}), encoding="utf-8")

    current_time = 1000.0
    read_count = {"n": 0}

    original_open = open

    def counting_open(file, *args, **kwargs):
        read_count["n"] += 1
        return original_open(file, *args, **kwargs)

    monkeypatch.setattr(time, "monotonic", lambda: current_time)
    monkeypatch.setattr("builtins.open", counting_open)

    first = load_json_config(str(config_file), ttl_seconds=30)
    second = load_json_config(str(config_file), ttl_seconds=30)

    assert first == {"version": 1}
    assert second == {"version": 1}
    assert read_count["n"] == 1

    config_file.write_text(json.dumps({"version": 2}), encoding="utf-8")
    still_cached = load_json_config(str(config_file), ttl_seconds=30)
    assert still_cached == {"version": 1}
    assert read_count["n"] == 1

    current_time += 31.0
    refreshed = load_json_config(str(config_file), ttl_seconds=30)
    assert refreshed == {"version": 2}
    assert read_count["n"] == 2


def test_invalidate_json_config_forces_reload(tmp_path, monkeypatch):
    config_file = tmp_path / "test_config.json"
    config_file.write_text(json.dumps({"flag": True}), encoding="utf-8")

    current_time = 2000.0
    read_count = {"n": 0}

    original_open = open

    def counting_open(file, *args, **kwargs):
        read_count["n"] += 1
        return original_open(file, *args, **kwargs)

    monkeypatch.setattr(time, "monotonic", lambda: current_time)
    monkeypatch.setattr("builtins.open", counting_open)

    assert load_json_config(str(config_file), ttl_seconds=30) == {"flag": True}
    assert read_count["n"] == 1

    config_file.write_text(json.dumps({"flag": False}), encoding="utf-8")
    invalidate_json_config(str(config_file))

    assert load_json_config(str(config_file), ttl_seconds=30) == {"flag": False}
    assert read_count["n"] == 2


def test_load_json_config_missing_file_returns_empty_dict(tmp_path):
    missing = tmp_path / "missing.json"
    assert not missing.exists()
    assert load_json_config(str(missing), ttl_seconds=30) == {}
