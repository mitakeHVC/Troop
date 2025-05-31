import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session as SQLAlchemySession
from typing import Generator
import os # For environment variable, though not used in this simplified version

# Import main app and Base for models
from app.main import app
from app.db.base import Base
from app.db.session import get_db # Original get_db dependency

# --- Test Database Setup ---
# Use an in-memory SQLite database for testing
TEST_SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    TEST_SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False} # Required for SQLite
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Fixture to create all tables before test session and drop after
@pytest.fixture(scope="session", autouse=True)
def apply_migrations_for_session(): # Renamed to avoid potential clash if user has own 'apply_migrations'
    # Create all tables for the test database.
    # For a more complex setup with multiple test DBs or Alembic, this would be different.
    Base.metadata.create_all(bind=engine) # Create tables based on SQLAlchemy models
    yield
    Base.metadata.drop_all(bind=engine) # Drop tables after the entire test session

# Fixture to provide a database session for each test
@pytest.fixture()
def db_session() -> Generator[SQLAlchemySession, None, None]:
    connection = engine.connect()
    # Begin a transaction
    transaction = connection.begin()
    # Create a session for the test
    session = TestingSessionLocal(bind=connection)
    yield session
    # Rollback the transaction after the test is done
    session.close()
    transaction.rollback()
    connection.close()

# Fixture to provide a TestClient with overridden DB session for each test
@pytest.fixture()
def client(db_session: SQLAlchemySession) -> Generator[TestClient, None, None]:

    def override_get_db() -> Generator[SQLAlchemySession, None, None]:
        try:
            yield db_session
        finally:
            # The db_session fixture already handles closing the session
            pass

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    # Clean up the dependency override after the test client is done
    del app.dependency_overrides[get_db]
