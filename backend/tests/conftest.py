"""Pytest configuration — PostgreSQL fixture.

Per D-11: No SQLite fallback. Tests use united_agents_test database.
"""

import os
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Use test database
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg2://united_agents:changeme@localhost:5432/united_agents_test"
)


@pytest.fixture(scope="session")
def engine():
    """Create a test engine connected to the test database."""
    eng = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    yield eng
    eng.dispose()


@pytest.fixture(scope="session")
def tables(engine):
    """Create all tables at the start of the test session, drop at the end."""
    from src.models import Base
    Base.metadata.create_all(engine)
    yield
    # Drop with raw SQL to handle circular FK
    from sqlalchemy import text
    with engine.connect() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
        conn.commit()


@pytest.fixture
def db_session(engine, tables):
    """Provide a transactional database session that rolls back after each test."""
    connection = engine.connect()
    transaction = connection.begin()
    Session = sessionmaker(bind=connection)
    session = Session()

    yield session

    session.close()
    transaction.rollback()
    connection.close()
