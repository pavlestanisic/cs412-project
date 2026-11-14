"""
DATA LAYER - where objects are stored.

We keep everything in memory (a Python dict). A real app could swap these
classes for database versions without changing the service layer, because
services only use the methods below (add / get / all / ...).

`Repository` is the shared base class (inheritance). The subclasses add a
few handy search methods for their own kind of object.
"""

from delivery.common.errors import NotFoundError, ValidationError


class Repository:
    """Simple in-memory storage keyed by `obj.id`."""

    # Human word for error messages, e.g. "order". Subclasses overwrite it.
    kind = "item"

    def __init__(self):
        self._items = {}  # id -> object

    def add(self, obj):
        """Store a new object. Ids must be unique."""
        if obj.id in self._items:
            raise ValidationError(f"A {self.kind} with id {obj.id} already exists.")
        self._items[obj.id] = obj
        return obj

    def get(self, obj_id):
        """Return the object with this id, or raise NotFoundError."""
        if obj_id not in self._items:
            raise NotFoundError(f"No {self.kind} with id {obj_id}.")
        return self._items[obj_id]

    def all(self):
        """All stored objects, in the order they were added."""
        return list(self._items.values())

    def count(self):
        """How many objects are stored."""
        return len(self._items)


class CustomerRepository(Repository):
    """Stores customers."""

    kind = "customer"


class RestaurantRepository(Repository):
    """Stores restaurants."""

    kind = "restaurant"


class CourierRepository(Repository):
    """Stores couriers."""

    kind = "courier"

    def free_couriers(self):
        """Couriers that are not carrying an order."""
        return [courier for courier in self.all() if courier.is_free]


class OrderRepository(Repository):
    """Stores orders and hands out new order numbers."""

    kind = "order"

    def next_id(self):
        """
        The number the NEXT stored order should get: 1, 2, 3, ...

        Orders are never deleted, so "how many we have + 1" is always unused.
        Asking for it does not reserve it, so a failed order leaves no gap.
        """
        return self.count() + 1

    def by_state(self, state_name):
        """All orders whose state name is `state_name` (e.g. 'NEW')."""
        return [order for order in self.all() if order.state_name == state_name]
