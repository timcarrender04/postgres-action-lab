"""
How the API holds a conversation with Postgres.

The engine is a pool of connections. The URL is built from `.env`:
user, password, host, port, and database name. Compose reads that
file and puts the same names in this process. The host is `db`, the
Postgres service. That name exists on the Compose network only. On
the laptop, the same database is localhost port 5432, which Compose
publishes.

A session is one request's work. get_db opens it and closes it when
the request ends, including when the route raises. Closing the session
returns the connection to the pool.

create_all is not in this file. It has to run after models.py is
imported, because the engine only creates tables that are already
registered on Base. That call lives in main.py.
"""

import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# Fills the names below when this process is started on the laptop.
# Inside the API container Compose has already set them, and
# load_dotenv leaves an existing variable alone.
load_dotenv()

# No defaults on purpose. A missing name should fail here, not later
# with a connection to the wrong host.
POSTGRES_USER = os.environ["POSTGRES_USER"]
POSTGRES_PASSWORD = os.environ["POSTGRES_PASSWORD"]
POSTGRES_HOST = os.environ["POSTGRES_HOST"]
POSTGRES_PORT = os.environ["POSTGRES_PORT"]
POSTGRES_DB = os.environ["POSTGRES_DB"]

DATABASE_URL = (
    f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}"
    f"@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
)

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
