from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine


@pytest.fixture(autouse=True)
def _patch_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure all tests write artifacts to a temp dir, never real data/."""
    import config

    test_data = tmp_path / "test_data"
    test_data.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(config, "DATA_DIR", test_data)
    monkeypatch.setattr(config, "DB_PATH", test_data / "test.sqlite")


@pytest.fixture(name="engine")
def engine_fixture(tmp_path: Path) -> Engine:
    db_path = tmp_path / "test.sqlite"
    engine = create_engine(f"sqlite:///{db_path}")
    import models  # noqa: F401  # register models with SQLModel.metadata

    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture(name="client")
def client_fixture(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> Generator[TestClient, None, None]:
    import db
    from main import app

    monkeypatch.setattr(db, "engine", engine)

    def override_get_session() -> Generator[Session, None, None]:
        with Session(engine) as session:
            yield session

    app.dependency_overrides[db.get_session] = override_get_session

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()
