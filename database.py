"""
How the API holds a conversation with Postgres.

The engine is a pool of connections. The URL comes from Compose.
The host in that URL is `db`, the Postgres service. That name exists
on the Compose network only. On the laptop, the same database is
localhost port 5432, which Compose publishes.

A session is one request's work. get_db opens it and closes it when
the request ends, including when the route raises. Closing the session
returns the connection to the pool.

create_all is not in this file. It has to run after models.py is
imported, because the engine only creates tables that are already
registered on Base. That call lives in main.py.
"""

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# Compose sets this. There is no default on purpose: a missing URL
# should fail here, not later with a connection to the wrong host.
DATABASE_URL = os.environ["DATABASE_URL"]

# echo stays off. The page shows the SQL for the room.
# Set echo=True to also print each statement in `docker compose logs api`.
engine = create_engine(DATABASE_URL, echo=False, future=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)
Base = declarative_base()


def get_db():
    """One session for this request. Always closed."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
