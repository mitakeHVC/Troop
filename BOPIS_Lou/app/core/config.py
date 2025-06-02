from pydantic_settings import BaseSettings
from pydantic import AnyHttpUrl # Keep AnyHttpUrl from pydantic if used
from typing import List, Optional

class Settings(BaseSettings):
    PROJECT_NAME: str = "BOPIS/POS API"
    API_V1_STR: str = "/api/v1"

    # Database
    #SQLALCHEMY_DATABASE_URL: str = "sqlite:///./test.db" # For SQLite
    SQLALCHEMY_DATABASE_URL: str = "postgresql://user:password@localhost:5432/bopis_db" # Placeholder for PostgreSQL

    # JWT Settings
    SECRET_KEY: str = "YOUR_SECRET_KEY"  # CHANGE THIS!
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    class Config:
        case_sensitive = True
        # env_file = ".env" # If using a .env file

settings = Settings()
