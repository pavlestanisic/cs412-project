import sqlite3

from delivery.common.errors import NotFoundError, ValidationError
from delivery.common.location import Location
from delivery.common.people import Customer
from delivery.storage.database import get_connection


class CustomerRepository:
    """Store and retrieve customers using SQLite."""

    def add(self, customer):
        """Save a customer and return the supplied object."""
        try:
            with get_connection() as connection:
                connection.execute(
                    """
                    INSERT INTO customers (
                        id, name, address_x, address_y
                    )
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        customer.id,
                        customer.name,
                        customer.location.x,
                        customer.location.y,
                    ),
                )
        except sqlite3.IntegrityError as error:
            raise ValidationError(
                f"Cannot save customer '{customer.id}': "
                "the ID may already exist or the data is invalid."
            ) from error

        return customer

    def get(self, customer_id):
        """Find one customer or report that the ID does not exist."""
        with get_connection() as connection:
            row = connection.execute(
                """
                SELECT id, name, address_x, address_y
                FROM customers
                WHERE id = ?
                """,
                (customer_id,),
            ).fetchone()

        if row is None:
            raise NotFoundError(
                f"No customer with id {customer_id}."
            )

        return self._to_customer(row)

    def all(self):
        """Return all customers in a predictable order."""
        with get_connection() as connection:
            rows = connection.execute(
                """
                SELECT id, name, address_x, address_y
                FROM customers
                ORDER BY id
                """
            ).fetchall()

        customers = []

        for row in rows:
            customer = self._to_customer(row)
            customers.append(customer)

        return customers

    def count(self):
        """Return the number of stored customers."""
        with get_connection() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS total FROM customers"
            ).fetchone()

        return row["total"]

    @staticmethod
    def _to_customer(row):
        """Convert a database row into an existing domain object."""
        location = Location(
            row["address_x"],
            row["address_y"],
        )

        return Customer(
            row["id"],
            row["name"],
            location,
        )