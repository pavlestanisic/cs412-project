"""
REPOSITORY pattern - restaurants and their menus in SQLite
(works inside the caller's transaction). Prices are stored as whole cents.
"""

import sqlite3
from decimal import Decimal, InvalidOperation

from delivery.common.errors import NotFoundError, ValidationError
from delivery.common.location import Location
from delivery.common.people import MenuItem, Restaurant


class RestaurantRepository:
    """Store restaurants and their menus using SQLite."""

    def __init__(self, connection):
        self.connection = connection

    def add(self, restaurant):
        """Save a restaurant and its menu together."""
        try:
            connection = self.connection
            connection.execute(
                """
                INSERT INTO restaurants (
                    id, name, location_x, location_y
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    restaurant.id,
                    restaurant.name,
                    restaurant.location.x,
                    restaurant.location.y,
                ),
            )

            for item in restaurant.menu_items():
                price_cents = self._to_cents(item.price)

                connection.execute(
                    """
                    INSERT INTO menu_items (
                        restaurant_id, name, price_cents
                    )
                    VALUES (?, ?, ?)
                    """,
                    (
                        restaurant.id,
                        item.name,
                        price_cents,
                    ),
                )

        except sqlite3.IntegrityError as error:
            raise ValidationError(
                f"Cannot save restaurant '{restaurant.id}': "
                "the ID or a menu item may already exist, "
                "or the data is invalid."
            ) from error

        return restaurant

    def get(self, restaurant_id):
        """Find a restaurant and load its menu."""
        connection = self.connection
        row = connection.execute(
            """
            SELECT id, name, location_x, location_y
            FROM restaurants
            WHERE id = ?
            """,
            (restaurant_id,),
        ).fetchone()

        if row is None:
            raise NotFoundError(
                f"No restaurant with id {restaurant_id}."
            )

        return self._to_restaurant(connection, row)

    def all(self):
        """Return all restaurants with their available menu items."""
        connection = self.connection
        rows = connection.execute(
            """
            SELECT id, name, location_x, location_y
            FROM restaurants
            ORDER BY id
            """
        ).fetchall()

        restaurants = []

        for row in rows:
            restaurant = self._to_restaurant(connection, row)
            restaurants.append(restaurant)

        return restaurants

    def count(self):
        """Return the number of stored restaurants."""
        connection = self.connection
        row = connection.execute(
            "SELECT COUNT(*) AS total FROM restaurants"
        ).fetchone()

        return row["total"]

    @staticmethod
    def _to_cents(price):
        """Convert a positive price to cents without silently rounding."""
        try:
            amount = Decimal(str(price))
        except InvalidOperation as error:
            raise ValidationError(
                "Menu item price must be a number."
            ) from error

        if not amount.is_finite() or amount <= 0:
            raise ValidationError(
                "Menu item price must be a finite positive number."
            )

        cents = amount * 100

        if cents != cents.to_integral_value():
            raise ValidationError(
                "Menu item price must have no more than "
                "two decimal places."
            )

        return int(cents)

    @staticmethod
    def _to_restaurant(connection, row):
        """Convert restaurant and menu rows into domain objects."""
        location = Location(
            row["location_x"],
            row["location_y"],
        )

        menu_rows = connection.execute(
            """
            SELECT name, price_cents
            FROM menu_items
            WHERE restaurant_id = ? AND available = 1
            ORDER BY name
            """,
            (row["id"],),
        ).fetchall()

        menu = {}

        for menu_row in menu_rows:
            item = MenuItem(
                menu_row["name"],
                menu_row["price_cents"] / 100,
            )
            menu[item.name] = item

        return Restaurant(
            row["id"],
            row["name"],
            location,
            menu,
        )