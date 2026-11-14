"""
SERVICE LAYER - registering customers, restaurants and couriers.

Services are the "use cases" of the app. The presentation layer calls them
with plain values (ids, names, numbers). Services turn those values into
domain objects (using builders and factories) and store them in repositories.
"""

import logging

from delivery.common.builders import RestaurantBuilder
from delivery.common.couriers import CourierCreator
from delivery.common.location import Location
from delivery.common.people import Customer

log = logging.getLogger(__name__)


class CatalogService:
    """Adds and lists customers, restaurants and couriers."""

    def __init__(self, customers, restaurants, couriers):
        # Repositories are supplied by the application factory.
        self._customers = customers
        self._restaurants = restaurants
        self._couriers = couriers

    def add_customer(self, customer_id, name, x, y):
        """Register a customer living at grid point (x, y)."""
        customer = self._customers.add(Customer(customer_id, name, Location(x, y)))
        log.info("Added customer %s (%s)", name, customer_id)
        return customer

    def add_restaurant(self, restaurant_id, name, x, y, dishes):
        """
        Register a restaurant. `dishes` is a dict: dish name -> price.
        Uses the RestaurantBuilder (BUILDER pattern).
        """
        builder = RestaurantBuilder(restaurant_id).named(name).located_at(Location(x, y))
        for dish_name, price in dishes.items():
            builder.add_dish(dish_name, price)
        restaurant = self._restaurants.add(builder.build())
        log.info("Added restaurant %s (%s) with %d dishes", name, restaurant_id, len(dishes))
        return restaurant

    def hire_courier(self, vehicle, courier_id, name, x, y):
        """
        Hire a courier. `vehicle` is 'bike', 'car' or 'walking'.
        Uses the CourierCreator (FACTORY METHOD pattern).
        """
        creator = CourierCreator.for_vehicle(vehicle)
        courier = creator.hire(courier_id, name, Location(x, y))
        return self._couriers.add(courier)

    def customers(self):
        """All customers."""
        return self._customers.all()

    def restaurants(self):
        """All restaurants."""
        return self._restaurants.all()

    def couriers(self):
        """All couriers."""
        return self._couriers.all()
