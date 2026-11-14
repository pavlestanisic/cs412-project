"""
SERVICE LAYER - everything that happens to an order.

This class connects the pieces:
  * builds orders with OrderBuilder           (BUILDER)
  * attaches notifiers to each order          (OBSERVER)
  * moves orders through their states         (STATE)
  * asks a Dispatcher to pick a courier       (TEMPLATE METHOD)
  * stores orders in the OrderRepository      (DATA LAYER)
"""

import logging

from delivery.common.builders import OrderBuilder
from delivery.common.errors import InvalidStateError

log = logging.getLogger(__name__)


class OrderService:
    """Use cases: place, dispatch, pick up, deliver and cancel orders."""

    def __init__(self, orders, customers, restaurants, couriers, dispatcher, observers=()):
        self._orders = orders
        self._customers = customers
        self._restaurants = restaurants
        self._couriers = couriers
        self.dispatcher = dispatcher        # public: can be swapped at runtime
        self._observers = list(observers)   # attached to every new order

    # ----- creating -------------------------------------------------------

    def place_order(self, customer_id, restaurant_id, items, delivery="standard", note=""):
        """
        Create and store a new order.

        items    -- list of (dish name, quantity), e.g. [("Pizza", 2)]
        delivery -- 'standard' or 'express'
        """
        builder = (OrderBuilder(self._orders.next_id())
                   .for_customer(self._customers.get(customer_id))
                   .from_restaurant(self._restaurants.get(restaurant_id))
                   .with_delivery(delivery)
                   .with_note(note))
        for dish_name, quantity in items:
            builder.add_item(dish_name, quantity)
        order = builder.build()

        # Subscribe the same application-owned observers to this new order.
        # They receive events from all orders but use the supplied order object
        # to determine which customer, restaurant or log entry is involved.
        for observer in self._observers:
            order.attach(observer)
        self._orders.add(order)
        log.info("Placed order %s for %s, total %.2f", order.id, customer_id, order.total())
        order.notify("created")  # first event: tell everyone the order exists
        return order

    # ----- dispatching ----------------------------------------------------

    def dispatch_order(self, order_id):
        """Find a courier for one NEW order. Returns the courier or None."""
        order = self._orders.get(order_id)
        if order.state_name != "NEW":
            raise InvalidStateError(f"Order {order_id} is {order.state_name}, only NEW orders can be dispatched.")
        return self.dispatcher.dispatch(order, self._couriers.all())

    def dispatch_waiting_orders(self):
        """
        Try to dispatch every NEW order (oldest first).
        Returns a list of (order, courier) pairs that were matched.
        """
        matched = []
        for order in self._orders.by_state("NEW"):
            courier = self.dispatcher.dispatch(order, self._couriers.all())
            if courier is None:
                break  # nobody is free, the rest must wait too
            matched.append((order, courier))
        return matched

    # ----- moving an order forward ----------------------------------------

    def pick_up(self, order_id):
        """The courier collected the food."""
        order = self._orders.get(order_id)
        order.pick_up()
        return order

    def deliver(self, order_id):
        """The food reached the customer. The courier becomes free."""
        order = self._orders.get(order_id)
        order.deliver()                          # state check happens here first
        order.courier.finish_order(delivered=True)
        return order

    def cancel(self, order_id):
        """Cancel an order. If a courier had it, the courier becomes free."""
        order = self._orders.get(order_id)
        order.cancel()                           # state check happens here first
        if order.courier is not None:
            order.courier.finish_order(delivered=False)
        return order

    # ----- reading --------------------------------------------------------

    def get_order(self, order_id):
        """One order by id."""
        return self._orders.get(order_id)

    def all_orders(self):
        """Every order."""
        return self._orders.all()
