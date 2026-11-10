from sqlalchemy import create_engine

from alembic import context
from app import models  # noqa: F401  (registers the tables on Base.metadata)
from app.config import settings
from app.db import Base

with create_engine(settings.database_url).connect() as connection:
    context.configure(connection=connection, target_metadata=Base.metadata)
    with context.begin_transaction():
        context.run_migrations()
