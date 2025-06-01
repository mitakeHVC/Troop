import asyncio
import pytest
import httpx
from typing import Generator, Dict, Any, AsyncGenerator, Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session as SQLAlchemySession

from main import app # Main FastAPI app
from app.db.base import Base # SQLAlchemy Base
from app.db.session import get_db # Original get_db for overriding
from app.models.sql_models import UserRole, User as UserModel
from app.schemas.user_schemas import UserCreate, UserRoleEnum
from app.schemas.token_schemas import Token
from app.core.security import get_password_hash
from app.services.user_service import create_user as service_create_user # For direct user creation if needed

from .test_config import BASE_URL

TEST_SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:?cache=shared" # Use shared cache for in-memory across connections if needed by async client or direct access
engine = create_engine(
    TEST_SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="session", autouse=True)
def apply_migrations_for_e2e_session():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

@pytest.fixture()
def db_session() -> Generator[SQLAlchemySession, None, None]:
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)

    # Override the app's get_db dependency for this session
    original_get_db = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = lambda: session

    yield session

    session.close()
    transaction.rollback()
    connection.close()
    # Restore original dependency override
    if original_get_db:
        app.dependency_overrides[get_db] = original_get_db
    else:
        del app.dependency_overrides[get_db]

@pytest.fixture(scope="session")
def event_loop(request) -> Generator[asyncio.AbstractEventLoop, None, None]:
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

import pytest_asyncio # Add this import
from httpx import ASGITransport # Import ASGITransport

@pytest_asyncio.fixture() # Changed to pytest_asyncio.fixture
async def async_client(db_session: SQLAlchemySession) -> AsyncGenerator[httpx.AsyncClient, None]: # ensure db session is setup for app
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as client: # Corrected usage
        yield client

@pytest.fixture
def create_test_user_directly(db_session: SQLAlchemySession): # Removed async
    async def _create_test_user_directly(
        username: str,
        email: str,
        password: str,
        role: UserRoleEnum, # Use Pydantic enum for consistency
        tenant_id: Optional[int] = None,
        is_active: bool = True
    ) -> UserModel:
        user_in = UserCreate(
            username=username,
            email=email,
            password=password,
            role=role,
            tenant_id=tenant_id
        )
        # Directly use the service or model to create user, bypassing API for setup
        # This is because creating a superuser via API might not be available/desired
        db_user = UserModel(
            username=user_in.username,
            email=user_in.email,
            password_hash=get_password_hash(user_in.password),
            role=UserRole[role.value], # Convert Pydantic enum to DB enum
            tenant_id=user_in.tenant_id,
            is_active=is_active
        )
        db_session.add(db_user)
        db_session.commit()
        db_session.refresh(db_user)
        return db_user
    return _create_test_user_directly

@pytest.fixture
def get_auth_headers(async_client: httpx.AsyncClient): # Removed async
    async def _get_auth_headers(username: str, password: str) -> Dict[str, str]:
        login_data = {"username": username, "password": password}
        response = await async_client.post("/auth/login", data=login_data) # FastAPI typically uses form data for login
        response.raise_for_status() # Ensure login was successful
        tokens = Token(**response.json())
        return {"Authorization": f"Bearer {tokens.access_token}"}
    return _get_auth_headers

@pytest.fixture
def create_customer_user_via_api(async_client: httpx.AsyncClient): # Removed async
    async def _create_customer_user_via_api(
        username: str,
        email: str,
        password: str,
        role: UserRoleEnum = UserRoleEnum.customer, # Default to customer
        tenant_id: Optional[int] = None # Added tenant_id
    ) -> Dict[str, Any]: # Returns the JSON response from API
        user_data = {
            "username": username,
            "email": email,
            "password": password,
            "role": role.value, # Ensure enum value is passed
        }
        if tenant_id is not None: # Add tenant_id if provided
            user_data["tenant_id"] = tenant_id
        response = await async_client.post("/auth/register", json=user_data)
        response.raise_for_status()
        return response.json()
    return _create_customer_user_via_api
