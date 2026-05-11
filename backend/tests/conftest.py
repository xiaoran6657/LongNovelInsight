import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine


@pytest.fixture(name="engine")
def engine_fixture(tmp_path):
    db_path = tmp_path / "test.sqlite"
    engine = create_engine(f"sqlite:///{db_path}")
    import models  # noqa: F401  # register models with SQLModel.metadata

    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture(name="client")
def client_fixture(engine, tmp_path, monkeypatch):
    import config

    test_data = tmp_path / "test_data"
    test_data.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(config, "DATA_DIR", test_data)

    from db import get_session
    from main import app

    def override_get_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()
