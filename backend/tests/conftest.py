from __future__ import annotations

from collections.abc import AsyncIterator
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import Settings, get_settings
from app.core.db import Base
from app.core.models_registry import __all__ as _  # noqa: F401 - ensures models are imported
from app.main import create_app


# Override settings for test environment
@pytest.fixture(scope="session")
def test_settings() -> Settings:
    """Return settings configured for integration tests."""
    import os

    # Use test database URL from env or default to test database
    test_db_url = os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql+asyncpg://pingboard:pingboard@localhost:5433/pingboard_test",
    )
    test_redis_url = os.environ.get("TEST_REDIS_URL", "redis://localhost:6380/1")

    return Settings(
        ENV="test",
        DATABASE_URL=test_db_url,
        REDIS_URL=test_redis_url,
        JWT_SECRET="test-secret-key-that-is-at-least-32-chars-long",
        JWT_ALGORITHM="HS256",
        ACCESS_TOKEN_EXPIRE_MINUTES=15,
        REFRESH_TOKEN_EXPIRE_DAYS=30,
        AUTH_RATE_LIMIT=1000,  # Relaxed for tests
        PUBLIC_RATE_LIMIT=1000,
        WRITE_RATE_LIMIT=1000,
        CORS_ORIGINS=["http://localhost:5173"],
        FRONTEND_URL="http://localhost:5173",
    )


@pytest.fixture(scope="session")
async def test_engine(test_settings: Settings) -> AsyncIterator[AsyncEngine]:
    """Create a test database engine with schema."""
    engine = create_async_engine(
        test_settings.database_url_str,
        echo=False,
        pool_pre_ping=True,
    )

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Clean up
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def db_session(test_engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    """Provide a transactional database session for a test.

    Each test gets a fresh transaction that is rolled back at the end,
    ensuring complete isolation between tests.
    """
    async with test_engine.connect() as conn:
        # Begin a transaction
        trans = await conn.begin()
        # Create a session bound to this connection
        session_maker = async_sessionmaker(bind=conn, class_=AsyncSession, expire_on_commit=False)
        async with session_maker() as session:
            yield session
        # Rollback the transaction, cleaning up all changes
        await trans.rollback()


@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncIterator[AsyncClient]:
    """Create an async test client with the database session overridden."""

    def override_get_db() -> AsyncIterator[AsyncSession]:
        yield db_session

    app = create_app()
    app.dependency_overrides[get_settings] = lambda: test_settings
    # We need to override the db dependency - let's check how it's done in the app

    from app.core.db import get_db

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
async def client_without_db() -> AsyncIterator[AsyncClient]:
    """Create an async test client without database override (for health checks)."""
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# Helper fixtures for common test data
@pytest.fixture
def test_org_id() -> str:
    """Generate a test organization ID."""
    return str(uuid4())


@pytest.fixture
def test_user_email() -> str:
    """Generate a unique test user email."""
    return f"test_{uuid4().hex[:8]}@example.com"


@pytest.fixture
def test_user_password() -> str:
    """Return a test password."""
    return "TestPass123!"