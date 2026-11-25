import sqlite3
from contextlib import contextmanager

from delivery.common.couriers import CourierCreator
from delivery.common.errors import NotFoundError, ValidationError
from delivery.common.location import Location
from delivery.storage.database import get_connection


class CourierRepository:
    """Store and retrieve couriers using SQLite."""

    def __init__(self, connection=None):
        self.connection = connection

    @contextmanager
    def get_connection(self):
        """Provide a connection to the database, either the one passed in or a new one."""
        if self.connection is not None:
            yield self.connection
        else:
            with get_connection() as connection:
                yield connection

    def add(self, courier):
        """Save a courier and return the supplied object."""
        try:
            with self.get_connection() as connection:
                connection.execute(
                    """
                    INSERT INTO couriers (
                        id, name, vehicle, location_x, location_y                    )
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        courier.id,
                        courier.name,
                        courier.vehicle,
                        courier.location.x,
                        courier.location.y,
                    ),
                )
        except sqlite3.IntegrityError as error:
            raise ValidationError(
                f"Cannot save courier '{courier.id}': "
                "the ID may already exist or the data is invalid."
            ) from error
        return courier

    def get(self, courier_id):
        """Find one courier or report that the ID does not exist."""
        with self.get_connection() as connection:
            row = connection.execute(
                """
                SELECT id, name, vehicle, location_x, location_y
                FROM couriers
                WHERE id = ?
                """,
                (courier_id,),
            ).fetchone()

        if row is None:
            raise NotFoundError(f"No courier with id {courier_id}.")

        return self.to_courier(connection, row)


    def all(self):

        with self.get_connection() as connection:
            rows = connection.execute(
                """
                SELECT id, name, vehicle, location_x, location_y
                FROM couriers
                ORDER BY id
                """
            ).fetchall()

            couriers = []

            for row in rows:
                courier = self.to_courier(connection, row)
                couriers.append(courier)
        return couriers


    def update(self, courier):
        """Update a courier's information in the database."""
        try:
            with self.get_connection() as connection:
                result = connection.execute(
                    """
                    UPDATE couriers
                    SET name = ?, vehicle = ?, location_x = ?, location_y = ?
                    WHERE id = ?
                    """,
                    (
                        courier.name,
                        courier.vehicle,
                        courier.location.x,
                        courier.location.y,
                        courier.id,
                    ),
                )
                if result.rowcount == 0:
                    raise NotFoundError(f"No courier with id {courier.id}.")
            
        except sqlite3.IntegrityError as error:
            raise ValidationError(f"Cannot update courier '{courier.id}':"
            "the data is invalid.") from error    
        return courier


    def count(self):
        """Return the number of stored couriers."""
        with self.get_connection() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS total FROM couriers"
            ).fetchone()
        return row["total"]

    @staticmethod
    def to_courier(connection, row):
        location = Location(row["location_x"], row["location_y"])

        creator = CourierCreator.for_vehicle(row["vehicle"])

        courier = creator.create_courier(
            row["id"], row["name"], location,)

        delivered = connection.execute(
             """
            SELECT COUNT(*) AS total
            FROM orders
            WHERE courier_id = ? AND state = 'DELIVERED'
            """,
            (courier.id,),
            ).fetchone()

        courier.delivered_count = delivered["total"]

        return courier