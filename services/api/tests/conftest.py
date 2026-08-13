import os
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite:////tmp/clinicpass-pytest.db"
os.environ["UPLOAD_DIR"] = "/tmp/clinicpass-pytest-uploads"
os.environ["AI_PROVIDER"] = "fixture"

from fastapi.testclient import TestClient
import pytest
from app.db import Base, engine
from app.main import app


@pytest.fixture(autouse=True)
def clean_database():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield


@pytest.fixture
def client():
    with TestClient(app) as value:
        yield value
    Path("/tmp/clinicpass-pytest-uploads").mkdir(exist_ok=True)

