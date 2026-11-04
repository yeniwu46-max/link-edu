from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app import app
from extensions import db
import tenancy  # noqa: F401
import classroom_models  # noqa: F401
import rag.models  # noqa: F401
from rag.governance import KnowledgeAuditLog  # noqa: F401

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)
target_metadata = db.metadata


def run_migrations_offline():
    context.configure(url=app.config['SQLALCHEMY_DATABASE_URI'], target_metadata=target_metadata,
                      literal_binds=True, dialect_opts={'paramstyle': 'named'},
                      compare_type=True, render_as_batch=app.config['SQLALCHEMY_DATABASE_URI'].startswith('sqlite'))
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    configuration = config.get_section(config.config_ini_section, {})
    configuration['sqlalchemy.url'] = app.config['SQLALCHEMY_DATABASE_URI']
    connectable = engine_from_config(configuration, prefix='sqlalchemy.', poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata,
                          compare_type=True, render_as_batch=connection.dialect.name == 'sqlite')
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
