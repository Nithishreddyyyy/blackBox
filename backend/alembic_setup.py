"""
Alembic env — auto-generates migrations from SQLAlchemy models.
Run: alembic init alembic   (one-time setup)
     alembic revision --autogenerate -m "description"
     alembic upgrade head
"""

# This file documents the Alembic setup.
# For this MVP, tables are auto-created via Base.metadata.create_all() at startup.
# Migrate to Alembic when the schema stabilises.
