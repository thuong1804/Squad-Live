from alembic import context
from app.core.config import Settings
from app.db.session import make_engine
from app.models.entities import Base

config = context.config
url = Settings().database_url.get_secret_value()
target_metadata = Base.metadata


def run_migrations():
    if context.is_offline_mode():
        context.configure(
            url=url,
            target_metadata=target_metadata,
            literal_binds=True,
            dialect_opts={"paramstyle": "named"},
        )
        with context.begin_transaction():
            context.run_migrations()
        return
    provided = config.attributes.get("connection")
    if provided is not None:
        context.configure(connection=provided, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()
        return
    engine = make_engine(url)
    try:
        with engine.connect() as connection:
            context.configure(
                connection=connection, target_metadata=target_metadata, compare_type=True
            )
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


run_migrations()
