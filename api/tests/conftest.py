from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from contextlib import asynccontextmanager
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app
from app.services.seed import seed_database

ROOT = Path(__file__).resolve().parents[2]
WORKBOOK = ROOT / "outputs" / "01a1cbad-1a1e-7de1-899b-92bedce65edf" / "FleetMix_ERP_Operational_Dataset.xlsx"


@pytest.fixture
def db_session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    @event.listens_for(engine, "connect")
    def fk(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    db = factory()
    seed_database(db, path=WORKBOOK)
    yield db
    db.close(); Base.metadata.drop_all(engine); engine.dispose()


@pytest.fixture
def client(db_session):
    original_lifespan=app.router.lifespan_context
    @asynccontextmanager
    async def test_lifespan(_app):
        yield
    app.router.lifespan_context=test_lifespan
    def override_db():
        yield db_session
    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    app.router.lifespan_context=original_lifespan
