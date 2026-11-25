"""
SERVICE LAYER - everything that happens to an order.

This class connects the pieces:
  * builds orders with OrderBuilder           (BUILDER)
  * attaches notifiers to each order          (OBSERVER)
  * moves orders through their states         (STATE)
  * asks a Dispatcher to pick a courier       (TEMPLATE METHOD)
  * saves every change in SQLite              (DATA LAYER)

How one change works (see _save):
  1. open a transaction,
  2. change the objects (the order only RECORDS its event, nobody is told yet),
  3. write the change through the repositories,
  4. commit, then announce the recorded events to the observers.
If anything fails before the commit, the database rolls back, the changed
Python objects are thrown away and fresh copies are loaded from the database.
No observer hears about a change that was not saved.

Delivery guarantee: events are announced AT MOST ONCE. If the app crashes
after the commit but before step 4, the change is saved but its messages are
never shown. Event counts still come out right, because the next start reads
them from the saved history.

Orders must only change through this service. A change made directly on an
Order object is neither saved nor announced.
"""

import logging

from delivery.common.builders import OrderBuilder
from delivery.common.errors import InvalidStateError, NotFoundError
from delivery.storage.courier_repository import CourierRepository
from delivery.storage.data_loader import DataLoader
from delivery.storage.order_repository import OrderRepository

log = logging.getLogger(__name__)


class OrderService:
    """Use cases: place, dispatch, pick up, deliver and cancel orders."""

    def __init__(self, data, transactions, dispatcher, observers=()):
        """
        data         -- the application's LoadedData (shared with other services)
        transactions -- TransactionManager for the application's database
        """
        self._data = data
        self._transactions = transactions
        self.dispatcher = dispatcher
        self._observers = list(observers)

        # Restored orders hear about future actions too. Attaching does not
        # announce anything, so restoring never repeats old events.
        self._attach_observers_to_all_orders()

    # ----- creating -------------------------------------------------------

    def place_order(self, customer_id, restaurant_id, items, delivery="standard", note=""):
        """
        Create and store a new order.

        items    -- list of (dish name, quantity), e.g. [("Pizza", 2)]
        delivery -- 'standard' or 'express'
        """
        # SQLite assigns the real ID when the order is inserted.
        builder = (OrderBuilder(None)
                   .for_customer(self._find(self._data.customers, customer_id, "customer"))
                   .from_restaurant(self._find(self._data.restaurants, restaurant_id, "restaurant"))
                   .with_delivery(delivery)
                   .with_note(note))
        for dish_name, quantity in items:
            builder.add_item(dish_name, quantity)
        order = builder.build()  # wrong dishes etc. fail here, before any saving

        def change(connection):
            OrderRepository(connection).add(order)
            order.record_event("created")

        self._save(order, change)

        # The order exists only once it is saved; then it joins the others.
        self._data.orders[order.id] = order
        self._attach_observers(order)
        log.info("Placed order %s for %s, total %.2f", order.id, customer_id, order.total())
        self._publish(order)
        return order

    # ----- dispatching ----------------------------------------------------

    def dispatch_order(self, order_id):
        """Find a courier for one NEW order. Returns the courier or None."""
        order = self.get_order(order_id)
        if order.state_name != "NEW":
            raise InvalidStateError(f"Order {order_id} is {order.state_name}, only NEW orders can be dispatched.")
        return self._dispatch(order)

    def dispatch_waiting_orders(self):
        """
        Try to dispatch every NEW order (oldest first).
        Returns a list of (order, courier) pairs that were matched.

        Each order is saved in its own transaction, so an order that was
        matched stays matched even if a later one fails.
        """
        matched = []
        for order in self._orders_in_state("NEW"):
            courier = self._dispatch(order)
            if courier is None:
                break  # nobody is free, the rest must wait too
            matched.append((order, courier))
        return matched

    def _dispatch(self, order):
        """Assign the best free courier to `order` and save it."""
        def change(connection):
            courier = self.dispatcher.dispatch(order, list(self._data.couriers.values()))
            if courier is not None:
                OrderRepository(connection).save_transition(order, "NEW")
            return courier

        courier = self._save(order, change)
        self._publish(order)
        return courier

    # ----- moving an order forward ----------------------------------------

    def pick_up(self, order_id):
        """The courier collected the food."""
        order = self.get_order(order_id)

        def change(connection):
            order.pick_up()
            OrderRepository(connection).save_transition(order, "ASSIGNED")

        self._save(order, change)
        self._publish(order)
        return order

    def deliver(self, order_id):
        """The food reached the customer. The courier becomes free."""
        order = self.get_order(order_id)

        def change(connection):
            order.deliver()                          # state check happens here first
            courier = order.courier
            courier.finish_order(delivered=True)     # moves the courier to the customer
            CourierRepository(connection).update(courier)
            OrderRepository(connection).save_transition(order, "PICKED_UP")

        self._save(order, change)
        self._publish(order)
        return order

    def cancel(self, order_id):
        """Cancel an order. If a courier had it, the courier becomes free."""
        order = self.get_order(order_id)

        def change(connection):
            previous_state = order.state_name
            order.cancel()                           # state check happens here first
            if order.courier is not None:
                order.courier.finish_order(delivered=False)
            OrderRepository(connection).save_transition(order, previous_state)

        self._save(order, change)
        self._publish(order)
        return order

    # ----- reading --------------------------------------------------------

    def get_order(self, order_id):
        """Return one order."""
        return self._find(self._data.orders, order_id, "order")

    def all_orders(self):
        """Return every order, oldest first."""
        return list(self._data.orders.values())

    def _orders_in_state(self, state_name):
        """All orders whose state name is `state_name` (e.g. 'NEW'), oldest first."""
        return [order for order in self._data.orders.values() if order.state_name == state_name]

    @staticmethod
    def _find(objects_by_id, object_id, kind):
        """Look up an object by ID or raise NotFoundError."""
        found = objects_by_id.get(object_id)
        if found is None:
            raise NotFoundError(f"No {kind} with id {object_id}.")
        return found

    # ----- saving and announcing ------------------------------------------

    def _save(self, order, change):
        """
        Run `change(connection)` in one transaction and return its result.

        On failure the database rolls back by itself, but the Python objects
        that `change` touched do not. They are discarded by loading everything
        again, and the order's recorded events are dropped with them.
        """
        try:
            with self._transactions.transaction() as connection:
                return change(connection)
        except Exception:
            order.take_events()  # never announce events of an unsaved change
            self._reload()
            raise

    def _publish(self, order):
        """Announce the order's recorded events. Call only after a commit."""
        for event in order.take_events():
            order.notify(event)  # observer failures are logged, not raised

    def _reload(self):
        """Replace every loaded object with a fresh copy of the saved data."""
        with self._transactions.transaction() as connection:
            fresh = DataLoader(connection).load()
        self._data.replace_with(fresh)
        self._attach_observers_to_all_orders()
        log.warning("Change was rolled back; reloaded %d orders from the database.",
                    len(self._data.orders))

    def _attach_observers_to_all_orders(self):
        for order in self._data.orders.values():
            self._attach_observers(order)

    def _attach_observers(self, order):
        # The same application-owned observers listen to every order. They use
        # the order passed to update() to know which customer or kitchen is meant.
        for observer in self._observers:
            order.attach(observer)
