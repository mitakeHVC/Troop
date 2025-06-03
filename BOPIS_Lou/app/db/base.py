from sqlalchemy.orm import declarative_base

Base = declarative_base()
# Models will import this Base.
# All model classes will be imported directly in alembic/env.py
# to ensure they are registered with this Base instance when Alembic runs.
