"""Saving to SQLite and reading back gives the same values."""

import unittest

from delivery.common.couriers import CarCourier
from delivery.common.errors import NotFoundError, ValidationError
from delivery.common.location import Location
from delivery.common.people import Customer, MenuItem, Restaurant
from delivery.storage.courier_repository import CourierRepository
from delivery.storage.customer_repository import CustomerRepository
from delivery.storage.database import IN_MEMORY, connect, initialize_database
from delivery.storage.restaurant_repository import RestaurantRepository


class RepositoryTestCase(unittest.TestCase):

    def setUp(self):
        self.connection = connect(IN_MEMORY)
        self.addCleanup(self.connection.close)
        initialize_database(self.connection)

    def test_customer_round_trip(self):
        repository = CustomerRepository(self.connection)
        repository.add(Customer("C1", "Tara", Location(1.5, 2)))

        loaded = repository.get("C1")

        self.assertEqual(loaded.id, "C1")
        self.assertEqual(loaded.name, "Tara")
        self.assertEqual(loaded.location, Location(1.5, 2))

    def test_courier_round_trip_keeps_vehicle_type(self):
        repository = CourierRepository(self.connection)
        repository.add(CarCourier("K2", "Jelena", Location(8, 3)))

        loaded = repository.get("K2")

        self.assertIsInstance(loaded, CarCourier)
        self.assertEqual(loaded.name, "Jelena")
        self.assertEqual(loaded.location, Location(8, 3))
        self.assertTrue(loaded.is_free)
        self.assertEqual(loaded.delivered_count, 0)

    def test_courier_update_saves_new_location(self):
        repository = CourierRepository(self.connection)
        courier = repository.add(CarCourier("K2", "Jelena", Location(8, 3)))

        courier.location = Location(1, 1)
        repository.update(courier)

        self.assertEqual(repository.get("K2").location, Location(1, 1))

    def test_restaurant_round_trip_includes_menu(self):
        repository = RestaurantRepository(self.connection)
        menu = {"Pizza": MenuItem("Pizza", 8.50), "Cola": MenuItem("Cola", 2.00)}
        repository.add(Restaurant("R1", "Pizza Place", Location(2, 2), menu))

        loaded = repository.get("R1")

        self.assertEqual(loaded.name, "Pizza Place")
        self.assertEqual(
            [(item.name, item.price) for item in loaded.menu_items()],
            [("Cola", 2.00), ("Pizza", 8.50)],
        )

    def test_duplicate_id_is_a_validation_error(self):
        cases = [
            (CustomerRepository, Customer("C1", "Tara", Location(1, 1))),
            (CourierRepository, CarCourier("K1", "Marko", Location(1, 1))),
        ]
        for repository_class, obj in cases:
            with self.subTest(repository_class.__name__):
                repository = repository_class(self.connection)
                repository.add(obj)

                with self.assertRaises(ValidationError):
                    repository.add(obj)

                self.assertEqual(repository.count(), 1)

    def test_missing_id_is_not_found(self):
        with self.assertRaises(NotFoundError):
            CustomerRepository(self.connection).get("nobody")


if __name__ == "__main__":
    unittest.main()
