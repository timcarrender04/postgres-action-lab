"""
Item is the `items` table.

Postgres fills in `id`. The request supplies `name` and `price`.
`updated_at` changes when a row is inserted or updated. A GET does
not write, so it leaves `updated_at` alone.
"""

from sqlalchemy import Column, DateTime, Float, Integer, String, func

from database import Base


class Item(Base):
    __tablename__ = "items"

    # Postgres assigns this. The INSERT does not send an id.
    # After commit, refresh copies the new id back onto the object.
    # Skip refresh and the JSON says id: null while psql shows the row.
    id = Column(Integer, primary_key=True)

    # Both columns come from the JSON body of POST and PUT.
    name = Column(String(200), nullable=False)
    price = Column(Float, nullable=False)

    # Postgres writes this on INSERT through DEFAULT now().
    # An UPDATE from this app also sends now(), so the column moves
    # on a write and stays put on a GET.
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
