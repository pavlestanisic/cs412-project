import sqlite3
from decimal import Decimal, InvalidOperation

from pyparsing import line

from delivery.common.errors import NotFoundError, ValidationError
from delivery.common.delivery_options import get_delivery_factory
from delivery.common.location import Location
from delivery.common.order import Order, OrderLine
from delivery.common.order_states import(NewState, AssignedState, PickedUpState, DeliveredState, CancelledState)
from delivery.common.people import MenuItem



class OrderRepository:

    def __init__(self, connection):
        self.connection = connection

    def add(self, order):
        if order.state_name != "NEW" or order.courier is not None:
            raise ValidationError(
                f"Cannot save order '{order.id}': "
                "only new orders without a courier can be saved."
            )
        if not order.lines:
            raise ValidationError(
                f"Cannot save order '{order.id}': "
                "an order must be at least one item."
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

    def save_transition(self,order,previous_state):
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
                row = self.connection.execute("SELECT id FROM orders WHERE id = ?",
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
        """Convert a Decimal to an integer number of cents."""
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


    # Function used for loading. It must not call assign(), pick_up(), etc...
    # Those are used for new business actions
    def load_all():
        pass


    #Helper functions 
    @staticmethod
    def _check_couriers_are_fresh(couriers):
        for couriers in couriers.values():
            if courier.current_order is not None:
                raise ValidationError(
                    "Orders must be loaded with fresh courier objects."
                )

    def _read_order_rows(self):
        return self.connection.execute(
        """
        SELECT id, customer_id, restaurant_id, courier_id,
               state, delivery_option, delivery_x, delivery_y,
               delivery_fee_cents, note
        FROM orders
        ORDER BY id
        """
    ).fetchall()

    def _build_saved_order(self, row, couriers, customers, restaurants):
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