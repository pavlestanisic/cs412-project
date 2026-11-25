"""
Restarting the app on the same database file restores where it left off.

Each test works with one app, closes it, and opens a new app on the same
file. The new app knows only what was saved.

Sample city: customers C1 Tara (1,1), C2 Alice (5,5); restaurant R1 at (2,2);
couriers K1 bike (1,1), K2 car (8,8), K3 walking (4,4).
"""

import tempfile
import unittest
from pathlib import Path

from delivery.core.factory import build_app
from delivery.producer.sample_data import load_sample_data


class RestorationTestCase(unittest.TestCase):

    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.database = Path(folder.name) / "delivery.db"

    def start_app(self):
        """Open the app on the test database, like a fresh program start."""
        app = load_sample_data(build_app(database=self.database))
        self.addCleanup(app.close)
        return app

    def restart(self, app):
        app.close()
        return self.start_app()

    def test_placed_order_is_restored(self):
        app = self.start_app()
        placed = app.order_service.place_order(
            "C2", "R1", [("Pizza", 2), ("Cola", 1)], "express", "ring twice")

        app = self.restart(app)
        restored = app.order_service.get_order(placed.id)

        self.assertIsNot(restored, placed)
        self.assertEqual(restored.state_name, "NEW")
        self.assertEqual(restored.customer.name, "Alice")
        self.assertEqual(restored.delivery_option, "express")
        self.assertEqual(restored.note, "ring twice")
        self.assertEqual([repr(line) for line in restored.lines], ["2 x Pizza", "1 x Cola"])
        self.assertEqual(restored.total(), placed.total())
        self.assertIsNone(restored.courier)

    def test_assigned_order_is_linked_to_its_courier(self):
        app = self.start_app()
        order = app.order_service.place_order("C1", "R1", [("Pizza", 1)])
        courier = app.order_service.dispatch_order(order.id)

        app = self.restart(app)
        order = app.order_service.get_order(order.id)
        courier = app.catalog.get_courier(courier.id)

        self.assertEqual(order.state_name, "ASSIGNED")
        self.assertIs(order.courier, courier)
        self.assertIs(courier.current_order, order)
        self.assertEqual(app.health.problems(), [])

        # The busy courier must not get a second order after the restart.
        second = app.order_service.place_order("C1", "R1", [("Cola", 1)])
        self.assertIsNot(app.order_service.dispatch_order(second.id), courier)

    def test_delivered_order_restores_courier_progress(self):
        app = self.start_app()
        service = app.order_service
        order = service.place_order("C2", "R1", [("Pizza", 1)])
        courier = service.dispatch_order(order.id)
        service.pick_up(order.id)
        service.deliver(order.id)

        app = self.restart(app)
        courier = app.catalog.get_courier(courier.id)

        self.assertEqual(app.order_service.get_order(order.id).state_name, "DELIVERED")
        self.assertTrue(courier.is_free)
        self.assertEqual(courier.delivered_count, 1)
        self.assertEqual(courier.location, app.catalog.get_customer("C2").location)

    def test_cancelled_assigned_order_frees_its_courier(self):
        app = self.start_app()
        order = app.order_service.place_order("C1", "R1", [("Pizza", 1)])
        courier = app.order_service.dispatch_order(order.id)
        app.order_service.cancel(order.id)

        app = self.restart(app)
        courier = app.catalog.get_courier(courier.id)

        self.assertEqual(app.order_service.get_order(order.id).state_name, "CANCELLED")
        self.assertTrue(courier.is_free)
        self.assertEqual(courier.delivered_count, 0)

    def test_sample_data_is_not_added_twice(self):
        app = self.start_app()
        app = self.restart(app)

        self.assertEqual(len(app.catalog.customers()), 4)
        self.assertEqual(len(app.catalog.restaurants()), 3)
        self.assertEqual(len(app.catalog.couriers()), 3)


if __name__ == "__main__":
    unittest.main()
