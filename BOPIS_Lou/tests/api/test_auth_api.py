from fastapi.testclient import TestClient
from sqlalchemy.orm import Session as SQLAlchemySession
from app.schemas.user_schemas import UserCreate, UserRoleEnum # UserRoleEnum for providing role as string

def test_user_registration_and_login(client: TestClient, db_session: SQLAlchemySession):
    # Registration
    user_data = {
        "username": "testuser_auth_api", # Changed to avoid conflict with other tests if run in same DB
        "email": "testuser_auth_api@example.com",
        "password": "testpassword",
        "role": UserRoleEnum.customer.value # Use enum value for "customer"
        # tenant_id is not required for customer role by default in UserCreate
    }
    response = client.post("/auth/register", json=user_data)
    assert response.status_code == 201, response.text # Include response text on failure
    created_user = response.json()
    assert created_user["username"] == user_data["username"]
    assert created_user["email"] == user_data["email"]
    assert "id" in created_user

    # Login with username
    login_data_username = {"username": user_data["username"], "password": user_data["password"]}
    response_username_login = client.post("/auth/login", data=login_data_username) # OAuth2PasswordRequestForm uses form data
    assert response_username_login.status_code == 200, response_username_login.text
    tokens_username = response_username_login.json()
    assert "access_token" in tokens_username
    assert "refresh_token" in tokens_username
    assert tokens_username["token_type"] == "bearer"

    # Login with email
    login_data_email = {"username": user_data["email"], "password": user_data["password"]} # Use email as username
    response_email_login = client.post("/auth/login", data=login_data_email)
    assert response_email_login.status_code == 200, response_email_login.text
    tokens_email = response_email_login.json()
    assert "access_token" in tokens_email
    assert "refresh_token" in tokens_email
    assert tokens_email["token_type"] == "bearer"

    # Test registration with existing username
    response_dup_username = client.post("/auth/register", json=user_data)
    assert response_dup_username.status_code == 400 # Bad Request
    assert "Username already registered" in response_dup_username.text

    # Test registration with existing email
    user_data_dup_email = {
        "username": "anotheruser",
        "email": user_data["email"], # Same email
        "password": "testpassword",
        "role": UserRoleEnum.customer.value
    }
    response_dup_email = client.post("/auth/register", json=user_data_dup_email)
    assert response_dup_email.status_code == 400 # Bad Request
    assert "Email already registered" in response_dup_email.text

    # Test login with incorrect password
    login_data_wrong_pass = {"username": user_data["username"], "password": "wrongpassword"}
    response_wrong_pass = client.post("/auth/login", data=login_data_wrong_pass)
    assert response_wrong_pass.status_code == 401 # Unauthorized
    assert "Incorrect username, email, or password" in response_wrong_pass.text
