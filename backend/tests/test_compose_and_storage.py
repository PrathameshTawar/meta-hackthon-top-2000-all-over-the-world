import os
from pathlib import Path
import pytest
import yaml

from app.config import Settings


def test_docker_compose_uses_persistent_sqlite_and_no_insecure_db():
    repo_root = Path(__file__).resolve().parent.parent.parent
    compose_path = repo_root / "docker-compose.yml"
    assert compose_path.exists(), "docker-compose.yml must exist"

    with open(compose_path, "r", encoding="utf-8") as f:
        compose = yaml.safe_load(f)

    services = compose.get("services", {})

    # S-4: No exposed insecure Postgres service
    if "db" in services:
        db_service = services["db"]
        ports = db_service.get("ports", [])
        assert not ports, f"Insecure exposed ports found in db service: {ports}"
        env = db_service.get("environment", {})
        if isinstance(env, dict):
            assert "saath" not in env.get("POSTGRES_PASSWORD", ""), "Default password 'saath' must not be hardcoded in docker-compose.yml"

    # R-4: Backend uses persistent volume and SQLite
    assert "backend" in services, "backend service must exist"
    backend = services["backend"]
    backend_env = backend.get("environment", {})

    # Ensure SQLite URL in backend environment
    db_url = backend_env.get("DATABASE_URL", "")
    assert "sqlite" in db_url, f"Expected SQLite in DATABASE_URL, got: {db_url}"
    assert "/data" in db_url, "SQLite DB should reside in /data volume"

    checkpoints_path = backend_env.get("CHECKPOINTS_DB_PATH", "")
    assert checkpoints_path == "/data/checkpoints.db", f"Expected /data/checkpoints.db, got: {checkpoints_path}"

    # Volumes check
    volumes = backend.get("volumes", [])
    assert any("/data" in str(v) for v in volumes), "Backend must mount persistent volume to /data"


def test_settings_reads_checkpoints_db_path_from_env(monkeypatch):
    monkeypatch.setenv("CHECKPOINTS_DB_PATH", "/test/volume/checkpoints.db")
    s = Settings()
    assert s.checkpoints_db_path == "/test/volume/checkpoints.db"
