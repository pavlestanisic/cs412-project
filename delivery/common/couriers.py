
import logging
from abc import ABC, abstractmethod

from delivery.common.errors import InvalidStateError, ValidationError

log = logging.getLogger(__name__)


class Courier(ABC):
    """Base class for all couriers. Subclasses must say how fast they are."""

    # Short text used in output, e.g. "bike". Subclasses overwrite it.
    vehicle = "unknown"

    def __init__(self, courier_id, name, location):
        if not name:
            raise ValidationError("Courier needs a name.")
        self.id = courier_id
        self.name = name
        self.location = location
        self._current_order = None  # None means the courier is free
        self.delivered_count = 0    # how many orders this courier delivered

    @abstractmethod
    def speed(self):
        """Speed in km per hour. Every courier type returns its own value."""

    @property
    def current_order(self):
        """The order the courier is carrying now (or None)."""
        return self._current_order

    @property
    def is_free(self):
        """True when the courier has no order right now."""
        return self._current_order is None

    def take_order(self, order):
        """Give an order to this courier. A courier carries one order at a time."""
        if not self.is_free:
            raise InvalidStateError(f"Courier {self.name} is already busy.")
        self._current_order = order
        log.debug("Courier %s took order %s", self.id, order.id)

    def finish_order(self, delivered):
        """
        Free the courier.

        delivered -- True if the food reached the customer (counts it),
                     False if the order was cancelled.
        """
        if self.is_free:
            raise InvalidStateError(f"Courier {self.name} has no order to finish.")
        if delivered:
            self.delivered_count += 1
            # After delivery the courier stands at the customer's door.
            self.location = self._current_order.customer.location
        log.debug("Courier %s finished order %s", self.id, self._current_order.id)
        self._current_order = None

    def travel_minutes(self, distance_km):
        """How many minutes this courier needs to ride `distance_km`."""
        return round(distance_km / self.speed() * 60)

    def __repr__(self):
        return f"{type(self).__name__}({self.id}, {self.name})"


class BikeCourier(Courier):
    """Courier on a bicycle: 15 km/h."""

    vehicle = "bike"

    def speed(self):
        return 15


class CarCourier(Courier):
    """Courier in a car: 30 km/h."""

    vehicle = "car"

    def speed(self):
        return 30


class WalkingCourier(Courier):
    """Courier on foot: 5 km/h."""

    vehicle = "walking"

    def speed(self):
        return 5


# ---------------------------------------------------------------------------
# FACTORY METHOD pattern
#
# `CourierCreator` has a normal method `hire()` that does the shared work
# (create + log). The *creation* step is the abstract "factory method"
# `create_courier()`. Each subclass decides WHICH courier class to create.
# Code that hires couriers only talks to CourierCreator and never needs to
# know the concrete classes.
# ---------------------------------------------------------------------------


class CourierCreator(ABC):
    """Creator in the Factory Method pattern."""

    @abstractmethod
    def create_courier(self, courier_id, name, location):
        """THE factory method: subclasses return a concrete Courier."""

    def hire(self, courier_id, name, location):
        """Shared logic around the factory method: create, then log."""
        courier = self.create_courier(courier_id, name, location)
        log.info("Hired %s courier %s (%s)", courier.vehicle, courier.name, courier.id)
        return courier

    @staticmethod
    def for_vehicle(vehicle):
        """Pick the right creator for a vehicle name like 'bike'."""
        creators = {
            "bike": BikeCourierCreator,
            "car": CarCourierCreator,
            "walking": WalkingCourierCreator,
        }
        if vehicle not in creators:
            raise ValidationError(f"Unknown vehicle '{vehicle}'. Use one of {sorted(creators)}.")
        return creators[vehicle]()


class BikeCourierCreator(CourierCreator):
    """Creates bike couriers."""

    def create_courier(self, courier_id, name, location):
        return BikeCourier(courier_id, name, location)


class CarCourierCreator(CourierCreator):
    """Creates car couriers."""

    def create_courier(self, courier_id, name, location):
        return CarCourier(courier_id, name, location)


class WalkingCourierCreator(CourierCreator):
    """Creates walking couriers."""

    def create_courier(self, courier_id, name, location):
        return WalkingCourier(courier_id, name, location)
