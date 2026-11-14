"""
BUILDER pattern - step by step creation of complex objects.

An Order needs many parts (customer, restaurant, several items, delivery
option, note). Passing all of that into one constructor is hard to read.
A builder lets us write:

    order = (OrderBuilder(1)
             .for_customer(ana)
             .from_restaurant(pizza_place)
             .add_item("Pizza", 2)
             .with_delivery("express")
             .build())

`build()` checks that everything needed was given before creating the object.
Each `with_...`/`add_...` method returns `self` so calls can be chained.
"""

from delivery.common.delivery_options import StandardDeliveryFactory, get_delivery_factory
from delivery.common.errors import ValidationError
from delivery.common.order import Order, OrderLine
from delivery.common.people import MenuItem, Restaurant


class OrderBuilder:
    """Builds one Order step by step."""

    def __init__(self, order_id):
        self._order_id = order_id
        self._customer = None
        self._restaurant = None
        self._wanted_items = []  # list of (item name, quantity)
        self._delivery_factory = StandardDeliveryFactory()  # default option
        self._note = ""

    def for_customer(self, customer):
        """Who orders."""
        self._customer = customer
        return self

    def from_restaurant(self, restaurant):
        """Where the food comes from."""
        self._restaurant = restaurant
        return self

    def add_item(self, item_name, quantity=1):
        """Add a dish by its menu name."""
        if quantity < 1:
            raise ValidationError(f"Quantity of '{item_name}' must be at least 1.")
        self._wanted_items.append((item_name, quantity))
        return self

    def with_delivery(self, option_name):
        """Pick 'standard' or 'express' (uses the ABSTRACT FACTORY)."""
        self._delivery_factory = get_delivery_factory(option_name)
        return self

    def with_note(self, note):
        """Free text for the courier, e.g. 'ring twice'."""
        self._note = note
        return self

    def build(self):
        """Check all parts and create the Order."""
        if self._customer is None:
            raise ValidationError("Order needs a customer.")
        if self._restaurant is None:
            raise ValidationError("Order needs a restaurant.")
        if not self._wanted_items:
            raise ValidationError("Order needs at least one item.")

        # Turn the item names into real menu items (raises if not on menu).
        lines = [
            OrderLine(self._restaurant.get_item(name), quantity)
            for name, quantity in self._wanted_items
        ]
        return Order(
            self._order_id,
            self._customer,
            self._restaurant,
            lines,
            self._delivery_factory,
            self._note,
        )


class RestaurantBuilder:
    """Builds one Restaurant with its menu step by step."""

    def __init__(self, restaurant_id):
        self._restaurant_id = restaurant_id
        self._name = None
        self._location = None
        self._menu = {}  # dish name -> MenuItem

    def named(self, name):
        """Restaurant name."""
        self._name = name
        return self

    def located_at(self, location):
        """Where the restaurant is."""
        self._location = location
        return self

    def add_dish(self, name, price):
        """Put one dish on the menu."""
        if name in self._menu:
            raise ValidationError(f"Dish '{name}' is already on the menu.")
        self._menu[name] = MenuItem(name, price)
        return self

    def build(self):
        """Check all parts and create the Restaurant."""
        if not self._name:
            raise ValidationError("Restaurant needs a name.")
        if self._location is None:
            raise ValidationError("Restaurant needs a location.")
        if not self._menu:
            raise ValidationError("Restaurant needs at least one dish.")
        return Restaurant(self._restaurant_id, self._name, self._location, self._menu)
