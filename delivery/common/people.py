"""
Customer and Restaurant (plus the MenuItem a restaurant sells).

These are plain data objects with a little validation.
"""

from delivery.common.errors import ValidationError


class MenuItem:
    """One dish on a menu, e.g. 'Pizza' for 8.50."""

    def __init__(self, name, price):
        # Validate early so a bad item can never exist.
        if not name:
            raise ValidationError("Menu item needs a name.")
        if price <= 0:
            raise ValidationError(f"Price of '{name}' must be above zero.")
        self.name = name
        self.price = price

    def __repr__(self):
        return f"MenuItem({self.name}, {self.price:.2f})"


class Customer:
    """A person who orders food."""

    def __init__(self, customer_id, name, location):
        if not name:
            raise ValidationError("Customer needs a name.")
        self.id = customer_id
        self.name = name
        self.location = location

    def __repr__(self):
        return f"Customer({self.id}, {self.name})"


class Restaurant:
    """A place that cooks food. Build it with RestaurantBuilder."""

    def __init__(self, restaurant_id, name, location, menu):
        # `menu` is a dict: dish name -> MenuItem.
        self.id = restaurant_id
        self.name = name
        self.location = location
        self._menu = dict(menu)  # copy so outside code cannot change it

    def get_item(self, item_name):
        """Return the MenuItem with this name, or raise if not on the menu."""
        if item_name not in self._menu:
            raise ValidationError(f"'{item_name}' is not on the menu of {self.name}.")
        return self._menu[item_name]

    def menu_items(self):
        """Return all menu items as a list (sorted by name for stable output)."""
        return [self._menu[name] for name in sorted(self._menu)]

    def __repr__(self):
        return f"Restaurant({self.id}, {self.name})"
