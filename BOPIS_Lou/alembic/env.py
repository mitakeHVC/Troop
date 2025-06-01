from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
# --- START MODIFICATION ---
import os
import sys
# Add project root to sys.path to allow importing 'app'
# Assuming 'alembic' directory is directly under 'BOPIS_Lou'
# which means '..' points to 'BOPIS_Lou'
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.core.config import settings # For DB URL, will be used later
from app.db.base import Base  # Import the Base

# Crucially, import all your models here so they register with Base.metadata
from app.models.sql_models import Tenant, User, Product, Order, OrderItem, PickupTimeSlot, Lane, StaffAssignment, Notification
# Add any other models if they were missed.

target_metadata = Base.metadata
# --- END MODIFICATION ---

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    # Ensure the URL is configured from settings if available for offline mode too
    if settings.SQLALCHEMY_DATABASE_URL:
        url = settings.SQLALCHEMY_DATABASE_URL
    else:
        url = config.get_main_option("sqlalchemy.url")

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    # Set the sqlalchemy.url in the config object for Alembic from settings
    # This needs to be done before engine_from_config is called.
    if settings.SQLALCHEMY_DATABASE_URL:
        config.set_main_option('sqlalchemy.url', settings.SQLALCHEMY_DATABASE_URL)

    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        # Ensure the URL from settings is used if connectable is derived from ini
        # This is now handled by setting config.set_main_option above.
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
