from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest
from uvicorn_worker import UvicornWorker


@pytest.fixture
def conf(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    monkeypatch.setenv("PORT", "9123")
    monkeypatch.setenv("WEB_CONCURRENCY", "3")
    path = Path(__file__).resolve().parents[1] / "gunicorn.conf.py"
    spec = importlib.util.spec_from_file_location("gunicorn_conf_under_test", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_uses_the_port_and_workers_from_the_environment(conf: ModuleType) -> None:
    assert conf.bind == "0.0.0.0:9123"
    assert conf.workers == 3


def test_worker_class_is_uvicorn_and_hides_the_server_header(conf: ModuleType) -> None:
    assert issubclass(conf.worker_class, UvicornWorker)
    assert conf.worker_class.CONFIG_KWARGS["server_header"] is False


def test_access_log_is_off_because_the_app_writes_its_own_json_line(conf: ModuleType) -> None:
    assert conf.accesslog is None
    assert conf.errorlog == "-"


def test_gunicorn_own_messages_are_json_and_redacted(
    conf: ModuleType, capsys: pytest.CaptureFixture[str]
) -> None:
    import json

    from gunicorn.config import Config

    assert conf.logger_class is conf.JsonLogger
    logger = conf.JsonLogger(Config())
    capsys.readouterr()
    logger.info("Listening at: postgresql://svc:LEAKED-PASSWORD@db/app (1)")
    (line,) = capsys.readouterr().out.splitlines()
    record = json.loads(line)
    assert record["logger"] == "gunicorn.error"
    assert "LEAKED-PASSWORD" not in line
    assert "svc:***@db/app" in record["event"]


def test_worker_freezes_the_startup_heap_out_of_the_garbage_collector(conf: ModuleType) -> None:
    import gc

    try:
        conf.post_worker_init(object())
        assert gc.get_freeze_count() > 0
    finally:
        gc.unfreeze()
