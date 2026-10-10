from __future__ import annotations

import pytest

from job_assistant.config import Config
from job_assistant.db import init_db
from job_assistant.repository import Repository
from job_assistant.web import create_app


class TestConfig(Config):
    TESTING = True
    SECRET_KEY = "test-secret"


@pytest.fixture
def app(tmp_path):
    TestConfig.DATABASE = tmp_path / "test.sqlite"
    TestConfig.RESUME_DIR = tmp_path / "resumes"
    init_db(TestConfig.DATABASE)
    app = create_app(TestConfig)
    return app


@pytest.fixture
def repo(app):
    return Repository(app.config["DATABASE"])


@pytest.fixture
def client(app):
    return app.test_client()

