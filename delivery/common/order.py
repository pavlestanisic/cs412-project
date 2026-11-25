"""
The Order - the heart of the app.

An Order is:
  * a SUBJECT (Observer pattern): it tells observers about every change.
  * a CONTEXT (State pattern): it keeps a state object and forwards the
    actions assign / pick_up / deliver / cancel to it.

Create orders with `OrderBuilder` (see builders.py), not directly.
"""

import logging

from delivery.common.observer import Subject
from delivery.common.order_states import NewState

from delivery.common.location import Location
from delivery.common.people import MenuItem

log = logging.getLogger(__name__)


class OrderLine:
    """One row of an order: a menu item and how many of it."""

    def __init__(self, item, quantity):
        self.item = MenuItem(item.name, item.price)  
        self.quantity = quantity

    def total(self):
        """Price of this row = item price x quantity."""
        return round(self.item.price * self.quantity, 2)

    def __repr__(self):
        return f"{self.quantity} x {self.item.name}"


class Order(Subject):
    """A customer's food order."""

    def __init__(self, order_id, customer, restaurant, lines, delivery_factory, note="",
                delivery_location=None, delivery_fee=None):
        
        super().__init__()  # sets up the observer list (from Subject)
        self.id = order_id
        self.customer = customer
        self.restaurant = restaurant
        self.lines = list(lines)
        self.note = note

        if delivery_location is None:
            delivery_location = customer.location   

        # Copy the destination so customer edits do not change it 
        self.delivery_location = Location(delivery_location.x, delivery_location.y)  

        # ABSTRACT FACTORY in use: the factory gives us a MATCHING pair.
        self.delivery_option = delivery_factory.name
        self._price_calculator = delivery_factory.create_price_calculator()
        self._time_estimator = delivery_factory.create_time_estimator()

        if delivery_fee is None:
            delivery_fee = self._price_calculator.delivery_fee(self.distance_km())

        self._delivery_fee = delivery_fee

        self._state = NewState()  # every order starts as NEW
        self._courier = None

    # ----- read-only information ------------------------------------------

    @property
    def state(self):
        """Current state object (NewState, AssignedState, ...)."""
        return self._state

    @property
    def state_name(self):
        """Current state as text, e.g. 'NEW'."""
        return self._state.name

    @property
    def courier(self):
        """The courier delivering this order (None until assigned)."""
        return self._courier

    def distance_km(self):
        """Street distance from the restaurant to the customer."""
        return self.restaurant.location.distance_to(self.delivery_location)

    def food_total(self):
        """Sum of all order lines."""
        return round(sum(line.total() for line in self.lines), 2)

    def delivery_fee(self):
        """Fee from the price calculator of the chosen delivery option."""
        return self._delivery_fee

    def total(self):
        """What the customer pays: food + delivery."""
        return round(self.food_total() + self.delivery_fee(), 2)

    def estimated_minutes(self, courier=None):
        """
        Minutes until the food arrives.

        Uses the given courier, or the assigned courier. The courier rides
        courier -> restaurant -> customer. Without any courier we only count
        restaurant -> customer by bike (a fair default guess).
        """
        courier = courier or self._courier
        if courier is None:
            travel = round(self.distance_km() / 15 * 60)  # 15 km/h = bike
        else:
            to_restaurant = courier.location.distance_to(self.restaurant.location)
            travel = courier.travel_minutes(to_restaurant + self.distance_km())
        return self._time_estimator.estimate_minutes(travel)

    # ----- actions: forwarded to the current STATE object -----------------

    def assign(self, courier):
        """Give this order to a courier (only allowed when NEW)."""
        self._state.assign(self, courier)

    def pick_up(self):
        """Courier collected the food (only allowed when ASSIGNED)."""
        self._state.pick_up(self)

    def deliver(self):
        """Food handed to customer (only allowed when PICKED_UP)."""
        self._state.deliver(self)

    def cancel(self):
        """Cancel the order (only allowed when NEW or ASSIGNED)."""
        self._state.cancel(self)

    # ----- helpers that ONLY state objects should call --------------------

    def set_courier(self, courier):
        """Remember which courier carries this order."""
        self._courier = courier

    def change_state(self, new_state, event):
        """Switch to `new_state` and tell all observers about `event`."""
        log.info("Order %s: %s -> %s", self.id, self._state.name, new_state.name)
        self._state = new_state
        # Announce the new order state immediately. This reports the order's
        # transition, not completion of the surrounding service operation:
        # assigning/releasing the courier may still happen after callbacks return.
        self.notify(event)

    def __repr__(self):
        return f"Order({self.id}, {self.state_name})"
