"""
SERVICE LAYER - registering customers, restaurants and couriers.

Services are the "use cases" of the app. The console and the web page call
them with plain values (ids, names, numbers). Services turn those values into
domain objects (using builders and factories) and save them in SQLite through
the repositories, one transaction per change.
"""

import logging

from delivery.common.builders import RestaurantBuilder
from delivery.common.couriers import CourierCreator
from delivery.common.errors import NotFoundError
from delivery.common.location import Location
from delivery.common.people import Customer
from delivery.storage.courier_repository import CourierRepository
from delivery.storage.customer_repository import CustomerRepository
from delivery.storage.restaurant_repository import RestaurantRepository

log = logging.getLogger(__name__)


class CatalogService:
    """Adds, finds and lists customers, restaurants and couriers."""

    def __init__(self, data, transactions):
        """
        data         -- the application's LoadedData (shared with OrderService)
        transactions -- TransactionManager for the application's database
        """
        self._data = data
        self._transactions = transactions

    # ----- adding ---------------------------------------------------------
    # Each new object is saved first and joins the loaded objects only after
    # the commit, so a failed save (e.g. duplicate ID) leaves nothing behind.

    def add_customer(self, customer_id, name, x, y):
        """Register a customer living at grid point (x, y)."""
        customer = Customer(customer_id, name, Location(x, y))
        with self._transactions.transaction() as connection:
            CustomerRepository(connection).add(customer)
        self._data.customers[customer.id] = customer
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
        restaurant = builder.build()
        with self._transactions.transaction() as connection:
            RestaurantRepository(connection).add(restaurant)
        self._data.restaurants[restaurant.id] = restaurant
        log.info("Added restaurant %s (%s) with %d dishes", name, restaurant_id, len(dishes))
        return restaurant

    def hire_courier(self, vehicle, courier_id, name, x, y):
        """
        Hire a courier. `vehicle` is 'bike', 'car' or 'walking'.
        Uses the CourierCreator (FACTORY METHOD pattern).
        """
        creator = CourierCreator.for_vehicle(vehicle)
        courier = creator.hire(courier_id, name, Location(x, y))
        with self._transactions.transaction() as connection:
            CourierRepository(connection).add(courier)
        self._data.couriers[courier.id] = courier
        return courier

    # ----- finding --------------------------------------------------------

    def get_customer(self, customer_id):
        """The customer with this ID, or NotFoundError."""
        return self._find(self._data.customers, customer_id, "customer")

    def get_restaurant(self, restaurant_id):
        """The restaurant with this ID, or NotFoundError."""
        return self._find(self._data.restaurants, restaurant_id, "restaurant")

    def get_courier(self, courier_id):
        """The courier with this ID, or NotFoundError."""
        return self._find(self._data.couriers, courier_id, "courier")

    @staticmethod
    def _find(objects_by_id, object_id, kind):
        found = objects_by_id.get(object_id)
        if found is None:
            raise NotFoundError(f"No {kind} with id {object_id}.")
        return found

    # ----- listing --------------------------------------------------------

    def customers(self):
        """All customers."""
        return list(self._data.customers.values())

    def restaurants(self):
        """All restaurants."""
        return list(self._data.restaurants.values())

    def couriers(self):
        """All couriers."""
        return list(self._data.couriers.values())
