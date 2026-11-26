import sqlite3
from decimal import Decimal, InvalidOperation

from delivery.common.errors import NotFoundError, ValidationError
from delivery.common.delivery_options import get_delivery_factory
from delivery.common.location import Location
from delivery.common.order import Order, OrderLine
from delivery.common.order_states import (NewState, AssignedState, PickedUpState,
                                          DeliveredState, CancelledState)
from delivery.common.people import MenuItem


class OrderRepository:
    """
    REPOSITORY pattern - orders, their items and their event history in SQLite.

    Every method uses the connection it was given and never commits:
    the caller's transaction decides when the changes become permanent.
    Each saved change also adds one row to order_events (the history).
    """

    def __init__(self, connection):
        self.connection = connection

    def add(self, order):
        """
        Save a NEW order with its items and a 'created' event.
        SQLite chooses the order's ID; it is written back to order.id.
        """
        if order.state_name != "NEW" or order.courier is not None:
            raise ValidationError(
                f"Cannot save order '{order.id}': "
                "only new orders without a courier can be saved."
            )
        if not order.lines:
            raise ValidationError(
                f"Cannot save order '{order.id}': "
                "an order must have at least one item."
            )

        try:
            result = self.connection.execute(
                """
                INSERT INTO orders (
                    customer_id,
                    restaurant_id,
                    state,
                    delivery_option,
                    delivery_x,
                    delivery_y,
                    delivery_fee_cents,
                    note
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    order.customer.id,
                    order.restaurant.id,
                    order.state_name,
                    order.delivery_option,
                    order.delivery_location.x,
                    order.delivery_location.y,
                    self._to_cents(order.delivery_fee()),
                    order.note,
                ),
            )
            order_id = result.lastrowid
            for line in order.lines:
                self._add_item(order_id, order.restaurant.id, line,)

            self._add_event(order_id, "created")
        except sqlite3.IntegrityError as error:
            raise ValidationError(
                f"Cannot save order '{order.id}': "
                "the ID may already exist or the data is invalid."
            ) from error

        order.id = order_id
        return order

    def save_transition(self, order, previous_state):
        """
        Save the order's new state and courier, plus the matching event.

        previous_state -- the state the order had before the change. The
        UPDATE only matches if the database still has that state, so a
        change made in the meantime (e.g. by another app) is not overwritten.
        """
        transition = {
            ("NEW", "ASSIGNED"): "assigned",
            ("NEW", "CANCELLED"): "cancelled",
            ("ASSIGNED", "PICKED_UP"): "picked_up",
            ("ASSIGNED", "CANCELLED"): "cancelled",
            ("PICKED_UP", "DELIVERED"): "delivered",
            }

        event = transition.get((previous_state, order.state_name))

        if event is None:
            raise ValidationError(
                f"Cannot save order '{order.id}': "
                f"invalid state transition from {previous_state} to {order.state_name}."
            )
        courier_id = None
        if order.courier is not None:
            courier_id = order.courier.id

        try:
            result = self.connection.execute(
                """
                UPDATE orders
                SET state = ?,
                    courier_id = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND state = ?
                """,
                (order.state_name, 
                    courier_id, 
                    order.id, 
                    previous_state,
                    ),
            )

            if result.rowcount == 0:
                # Nothing matched: either the order is gone, or its saved
                # state is no longer previous_state.
                row =self.connection.execute("SELECT id FROM orders WHERE id = ?",
                                               (order.id,)).fetchone()
                if row is None:
                    raise NotFoundError(f"No order with id {order.id}.")
                raise ValidationError(f"Order {order.id} has changed. "
                    "Reload it before trying again.")

            self._add_event(order.id, event)
        except sqlite3.IntegrityError as error:
            raise ValidationError(
                f"Cannot save order '{order.id}': "
                "the data is invalid."
            ) from error

        return order

    def event_counts(self):
        """How many times each event has been saved, e.g. {'created': 4}."""
        rows = self.connection.execute(
            """
            SELECT event, COUNT(*) AS total
            FROM order_events
            GROUP BY event
            """
        ).fetchall()

        counts = {}

        for row in rows:
            counts[row["event"]] = row["total"]

        return counts

    def _add_item(self, order_id, restaurant_id, line):
        """Save one ordered dish with its original price and quantity."""
        if type(line.quantity) is not int or line.quantity <= 0:
            raise ValidationError(
                "Order item quantity must be a positive integer."
            )

        menu_item = self.connection.execute(
            """
            SELECT id
            FROM menu_items
            WHERE restaurant_id = ?
            AND name = ?
            AND available = 1
            """,
            (restaurant_id, line.item.name),
        ).fetchone()

        if menu_item is None:
            raise ValidationError(
                f"Menu item '{line.item.name}' is unavailable "
                f"at restaurant '{restaurant_id}'."
            )

        price_cents = self._to_cents(line.item.price)

        if price_cents == 0:
            raise ValidationError(
                "An order item's price must be greater than zero."
            )

        self.connection.execute(
            """
            INSERT INTO order_items (
                order_id,
                menu_item_id,
                dish_name,
                unit_price_cents,
                quantity
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                order_id,
                menu_item["id"],
                line.item.name,
                price_cents,
                line.quantity,
            ),
    )
    
    def _add_event(self, order_id, event):
        """Record an order event within the current transaction."""
        self.connection.execute(
            """
            INSERT INTO order_events (order_id, event)
            VALUES (?, ?)
            """,
            (order_id, event),
        )

    @staticmethod
    def _to_cents(value):
        """Convert money (e.g. 3.5) to whole cents (350), refusing fractions of a cent."""
        try:
            amount = Decimal(str(value))
        except InvalidOperation as error:
            raise ValidationError(
                "Money must be a valid number."
            ) from error

        if not amount.is_finite() or amount < 0:
            raise ValidationError(
                "Money must be finite and nonnegative."
            )

        cents = amount * 100

        if cents != cents.to_integral_value():
            raise ValidationError(
                "Money must have no more than two decimal places."
            )

        return int(cents)


    # ----- restoring saved orders ----------------------------------------

    def load_all(self, customers, restaurants, couriers):
        """
        Rebuild every saved order (oldest first) as {id: Order}.

        customers, restaurants, couriers -- the objects already loaded, by ID.
        Orders are linked to these same objects, and each busy courier gets
        its order back.

        This must NOT call assign(), pick_up(), etc. Those are new actions:
        they would check the state rules and record events again. Instead
        the saved state and courier are put back directly, silently.
        """
        self._check_couriers_are_fresh(couriers)
        rows = self._read_order_rows()

        orders = {}

        for row in rows:
            order = self._build_saved_order(row, customers, restaurants)
            self._restore_state(order, row["state"])
            self._restore_courier(order, row["courier_id"], couriers)
            orders[order.id] = order

        return orders


    @staticmethod
    def _check_couriers_are_fresh(couriers):
        """Refuse couriers that already carry an order (they would be linked twice)."""
        for courier in couriers.values():
            if courier.current_order is not None:
                raise ValidationError(
                    "Orders must be loaded with fresh courier objects."
                )

    def _read_order_rows(self):
        """Every row of the orders table, oldest first."""
        return self.connection.execute(
        """
        SELECT id, customer_id, restaurant_id, courier_id,
               state, delivery_option, delivery_x, delivery_y,
               delivery_fee_cents, note
        FROM orders
        ORDER BY id
        """
    ).fetchall()


    def _load_items(self, order_id):
        """Restore the items saved with an order."""
        rows = self.connection.execute(
            """
            SELECT dish_name, unit_price_cents, quantity
            FROM order_items
            WHERE order_id = ?
            ORDER BY id
            """,
            (order_id,),
        ).fetchall()

        if not rows:
            raise ValidationError(
                f"Saved order {order_id} has no items."
            )

        lines = []

        for row in rows:
            if type(row["quantity"]) is not int or row["quantity"] <= 0:
                raise ValidationError(
                    f"Saved order {order_id} has an invalid quantity."
                )

            item = MenuItem(
                row["dish_name"],
                row["unit_price_cents"] / 100,
            )

            line = OrderLine(item, row["quantity"])
            lines.append(line)

        return lines

    
    def _build_saved_order(self, row, customers, restaurants):
        """
        Create the Order object for one row, still in state NEW.
        It keeps its saved address, fee and item prices, even if the
        customer moved or the menu prices changed since.
        """
        customer = customers.get(row["customer_id"])
        restaurant = restaurants.get(row["restaurant_id"])

        if customer is None or restaurant is None:
            raise ValidationError(
                f"Order {row['id']} references a missing customer or restaurant."
            )

        lines = self._load_items(row["id"])
        delivery_factory = get_delivery_factory(row["delivery_option"])
        destination = Location(row["delivery_x"], row["delivery_y"])

        return Order(
            order_id=row["id"],
            customer=customer,
            restaurant=restaurant,
            lines=lines,
            delivery_factory=delivery_factory,
            note=row["note"],
            delivery_location=destination,
            delivery_fee=row["delivery_fee_cents"] / 100.0,
        )

    @staticmethod
    def _restore_state(order, state_name):
        """Put the saved state object back, with no state check and no event."""
        state_classes = {
            "NEW": NewState,
            "ASSIGNED": AssignedState,
            "PICKED_UP": PickedUpState,
            "DELIVERED": DeliveredState,
            "CANCELLED": CancelledState,
        }

        state_class = state_classes.get(state_name)

        if state_class is None:
            raise ValidationError(
                f"Order {order.id} has an unknown state '{state_name}'."
            )

        order._state = state_class()

    @staticmethod
    def _restore_courier(order, courier_id, couriers):
        """
        Link the saved courier to the order. If the order is still active
        (ASSIGNED or PICKED_UP) the courier becomes busy with it again.
        Rows that break the courier rules are refused.
        """
        courier = None

        if courier_id is not None:
            courier = couriers.get(courier_id)

            if courier is None:
                raise ValidationError(
                    f"Order {order.id} references "
                    f"missing courier {courier_id}."
                )

        if order.state_name == "NEW" and courier is not None:
            raise ValidationError(
                f"Order {order.id} is NEW but has a courier."
            )

        requires_courier = order.state_name in (
            "ASSIGNED", "PICKED_UP", "DELIVERED"
        )

        if requires_courier and courier is None:
            raise ValidationError(
                f"Order {order.id} requires a courier."
            )

        is_active = order.state_name in ("ASSIGNED", "PICKED_UP")

        if is_active and not courier.is_free:
            raise ValidationError(
                f"Courier {courier.id} has multiple active orders."
            )

        order.set_courier(courier)

        if is_active:
            courier.take_order(order)