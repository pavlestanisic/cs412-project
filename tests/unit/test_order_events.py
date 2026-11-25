"""
Observers hear about a change only after it is saved, exactly once.

Sample city: customer C1 Tara, restaurant R1 Pizza Place,
nearest courier to R1 is K1 Marko (bike).
"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from delivery.common.errors import InvalidStateError, ValidationError
from delivery.common.observer import Observer, Subject
from delivery.core.factory import build_app
from delivery.producer.sample_data import load_sample_data
from delivery.storage.database import IN_MEMORY
from delivery.storage.order_repository import OrderRepository


class RecordingObserver(Observer):
    def __init__(self):
        self.events = []

    def update(self, order, event):
        self.events.append(event)


class BrokenObserver(Observer):
    def update(self, order, event):
        raise RuntimeError("observer is broken")


def saved_state(app, order_id):
    """The order's state as stored in the database, not in memory."""
    row = app.connection.execute(
        "SELECT state, courier_id FROM orders WHERE id = ?", (order_id,)
    ).fetchone()
    return row["state"], row["courier_id"]


class OrderEventsTestCase(unittest.TestCase):

    def setUp(self):
        self.app = load_sample_data(build_app(database=IN_MEMORY))
        self.addCleanup(self.app.close)
        self.service = self.app.order_service

    def test_full_lifecycle_messages_in_order(self):
        order = self.service.place_order("C1", "R1", [("Pizza", 1)])
        self.service.dispatch_order(order.id)
        self.service.pick_up(order.id)
        self.service.deliver(order.id)

        self.assertEqual(self.app.customer_notifier.messages, [
            f"[to Tara] Order #{order.id} received. Total {order.total():.2f}.",
            f"[to Tara] Marko (bike) will bring order #{order.id} in about 36 min.",
            f"[to Tara] Order #{order.id} is on the way!",
            f"[to Tara] Order #{order.id} delivered. Enjoy your meal!",
        ])
        self.assertEqual(self.app.restaurant_notifier.messages, [
            f"[to Pizza Place] Please cook order #{order.id}: 1 x Pizza.",
            f"[to Pizza Place] Marko will collect order #{order.id}.",
        ])

    def test_failed_save_rolls_back_and_announces_nothing(self):
        order = self.service.place_order("C1", "R1", [("Pizza", 1)])
        self.app.take_messages()

        with patch.object(OrderRepository, "save_transition", side_effect=RuntimeError("disk full")):
            with self.assertRaises(RuntimeError):
                self.service.dispatch_order(order.id)

        # Database: unchanged.
        self.assertEqual(saved_state(self.app, order.id), ("NEW", None))
        # Memory: the changed objects were replaced by the saved version.
        current = self.service.get_order(order.id)
        self.assertEqual(current.state_name, "NEW")
        self.assertIsNone(current.courier)
        self.assertTrue(all(courier.is_free for courier in self.app.catalog.couriers()))
        # Observers: nobody was told about the assignment.
        self.assertEqual(self.app.take_messages(), [])
        self.assertNotIn("assigned", self.app.event_log.event_counts)
        self.assertEqual(self.app.health.problems(), [])

        # The app keeps working, and the reloaded order still has its observers.
        self.service.dispatch_order(order.id)
        self.assertEqual(len(self.app.take_messages()), 2)

    def test_refused_action_changes_and_announces_nothing(self):
        order = self.service.place_order("C1", "R1", [("Pizza", 1)])
        self.service.dispatch_order(order.id)
        self.app.take_messages()

        with self.assertRaises(InvalidStateError):
            self.service.deliver(order.id)  # not picked up yet

        self.assertEqual(saved_state(self.app, order.id), ("ASSIGNED", "K1"))
        self.assertEqual(self.service.get_order(order.id).state_name, "ASSIGNED")
        self.assertEqual(self.app.take_messages(), [])

    def test_order_that_fails_to_build_is_not_saved(self):
        with self.assertRaises(ValidationError):
            self.service.place_order("C1", "R1", [("Burger", 1)])  # not on the menu

        self.assertEqual(self.service.all_orders(), [])
        self.assertEqual(self.app.take_messages(), [])

    def test_failing_observer_does_not_undo_the_saved_change(self):
        order = self.service.place_order("C1", "R1", [("Pizza", 1)])
        order.attach(BrokenObserver())

        with self.assertLogs("delivery.common.observer", "ERROR"):
            courier = self.service.dispatch_order(order.id)

        self.assertEqual(courier.id, "K1")
        self.assertEqual(saved_state(self.app, order.id), ("ASSIGNED", "K1"))
        self.assertEqual(self.app.event_log.event_counts["assigned"], 1)


class ObserverIsolationTestCase(unittest.TestCase):

    def test_failing_observer_does_not_stop_the_next_one(self):
        subject = Subject()
        after = RecordingObserver()
        subject.attach(BrokenObserver())
        subject.attach(after)

        with self.assertLogs("delivery.common.observer", "ERROR") as logs:
            subject.notify("created")

        self.assertEqual(after.events, ["created"])
        self.assertIn("BrokenObserver failed on event created", logs.output[0])


class EventsAcrossRestartTestCase(unittest.TestCase):

    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.database = Path(folder.name) / "delivery.db"

    def start_app(self):
        app = load_sample_data(build_app(database=self.database))
        self.addCleanup(app.close)
        return app

    def test_restoring_is_silent_and_restored_orders_still_notify(self):
        app = self.start_app()
        order = app.order_service.place_order("C1", "R1", [("Pizza", 1)])
        app.order_service.dispatch_order(order.id)
        app.close()

        app = self.start_app()
        self.assertEqual(app.take_messages(), [])  # restoring replays nothing

        app.order_service.pick_up(order.id)
        self.assertEqual(app.take_messages(), [f"[to Tara] Order #{order.id} is on the way!"])

    def test_event_counts_continue_without_double_counting(self):
        app = self.start_app()
        order = app.order_service.place_order("C1", "R1", [("Pizza", 1)])
        app.order_service.dispatch_order(order.id)
        app.close()

        app = self.start_app()
        self.assertEqual(app.event_log.event_counts, {"created": 1, "assigned": 1})

        app.order_service.pick_up(order.id)
        self.assertEqual(app.event_log.event_counts,
                         {"created": 1, "assigned": 1, "picked_up": 1})


if __name__ == "__main__":
    unittest.main()
