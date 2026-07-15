"""
tests/conftest.py
──────────────────
Shared pytest fixtures for all test modules.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.base import Base, get_db
from app.database.init_db import init_db
from app.main import app


# ─── Test Database ───────────────────────────────────────────

TEST_DATABASE_URL = "sqlite:///./test_linkedin_agent.db"

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_db():
    """Test database session dependency override."""
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    """Create test database tables before tests, drop after."""
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)
    test_engine.dispose()
    import os
    if os.path.exists("./test_linkedin_agent.db"):
        os.remove("./test_linkedin_agent.db")


@pytest.fixture()
def db():
    """Provide a clean database session for each test."""
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.rollback()
        db.close()


@pytest.fixture()
def client(db):
    """Provide a FastAPI test client with test DB."""
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ─── Mock Settings ───────────────────────────────────────────

@pytest.fixture()
def mock_settings(monkeypatch):
    """Mock settings with safe test values."""
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-123")
    monkeypatch.setenv("AI_PROVIDER", "openai")
    monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL)


# ─── Sample Data ─────────────────────────────────────────────

@pytest.fixture()
def sample_draft(db):
    """Create a sample draft in the test database."""
    from app.database.crud import create_draft
    draft = create_draft(
        db,
        topic="Artificial Intelligence",
        hook="🤖 AI is changing everything.",
        body="Here is how AI is transforming the industry...",
        cta="What do you think? Comment below!",
        content="🤖 AI is changing everything.\n\nHere is how AI is transforming the industry...\n\nWhat do you think? Comment below!",
        hashtags=["#AI", "#MachineLearning", "#Tech"],
        links=["https://openai.com", "https://ai.googleblog.com"],
        image_url="https://images.unsplash.com/photo-1677442135468-0fe9a0c13e22",
        image_source="unsplash",
        ai_provider="openai",
        ai_model="gpt-4o",
    )
    return draft
