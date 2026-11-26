"""
REPOSITORY pattern - couriers in SQLite (works inside the caller's transaction).

Only a courier's details and position are stored. Whether a courier is busy
is not a column: it follows from the orders table (see OrderRepository).
"""

import sqlite3

from delivery.common.couriers import CourierCreator
from delivery.common.errors import NotFoundError, ValidationError
from delivery.common.location import Location


class CourierRepository:
    """Store and retrieve couriers using SQLite."""

    def __init__(self, connection):
        self.connection = connection

    def add(self, courier):
        """Save a courier and return the supplied object."""
        try:
            self.connection.execute(
                """
                INSERT INTO couriers (
                    id, name, vehicle, location_x, location_y
                )
                VALUES (?, ?, ?, ?, ?)
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
        """Find a courier and restore their saved details."""
        row = self.connection.execute(
            """
            SELECT id, name, vehicle, location_x, location_y
            FROM couriers
            WHERE id = ?
            """,
            (courier_id,),
        ).fetchone()

        if row is None:
            raise NotFoundError(
                f"No courier with id {courier_id}."
            )

        return self.to_courier(self.connection, row)

    def all(self):
        """Return all couriers in a predictable order."""
        rows = self.connection.execute(
            """
            SELECT id, name, vehicle, location_x, location_y
            FROM couriers
            ORDER BY id
            """
        ).fetchall()

        couriers = []

        for row in rows:
            courier = self.to_courier(self.connection, row)
            couriers.append(courier)
        return couriers

    def update(self, courier):
        """Save a courier's name, vehicle and position (e.g. after a delivery)."""
        try:
            result = self.connection.execute(
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
        except sqlite3.IntegrityError as error:
            raise ValidationError(
                f"Cannot update courier '{courier.id}': "
                "the data is invalid."
            ) from error

        if result.rowcount == 0:
            raise NotFoundError(f"No courier with id {courier.id}.")
        return courier

    def count(self):
        """Return the number of stored couriers."""
        row = self.connection.execute(
            "SELECT COUNT(*) AS total FROM couriers"
        ).fetchone()
        return row["total"]

    @staticmethod
    def to_courier(connection, row):
        """
        Rebuild a free courier from a row.

        The delivered count is not stored separately: it is counted from the
        courier's DELIVERED orders, so it can never disagree with them.
        The current order is linked later by OrderRepository.load_all.
        """
        location = Location(row["location_x"], row["location_y"])

        creator = CourierCreator.for_vehicle(row["vehicle"])

        courier = creator.create_courier(
            row["id"], row["name"], location,
        )

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
