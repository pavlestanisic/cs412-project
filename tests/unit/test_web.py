"""
The web adapter: what the page receives, and the HTTP layer around it.

Sample city: customers C1 Tara..C4 Dusan, restaurant R1 Pizza Place,
nearest courier to R1 is K1 Marko.
"""

import json
import threading
import unittest
import urllib.error
import urllib.request

from delivery.common.errors import InvalidStateError, NotFoundError, ValidationError
from delivery.common.item_text import parse_items
from delivery.common.order_states import (AssignedState, CancelledState, DeliveredState,
                                          NewState, OrderState, PickedUpState)
from delivery.core.factory import build_app
from delivery.producer.sample_data import load_sample_data
from delivery.storage.database import IN_MEMORY
from delivery.web.server import WebApi, create_server


def actions_of(order_data):
    return [action["name"] for action in order_data["actions"]]


class WebApiTestCase(unittest.TestCase):

    def setUp(self):
        self.app = load_sample_data(build_app(database=IN_MEMORY))
        self.addCleanup(self.app.close)
        self.api = WebApi(self.app)
        self.service = self.app.order_service

    def test_state_lists_everything_the_page_shows(self):
        self.service.place_order("C1", "R1", [("Pizza", 1)])

        state = self.api.state()

        self.assertEqual([c["id"] for c in state["customers"]], ["C1", "C2", "C3", "C4"])
        pizza_place = state["restaurants"][0]
        self.assertEqual(pizza_place["name"], "Pizza Place")
        self.assertIn({"name": "Pizza", "price": 8.5}, pizza_place["menu"])
        self.assertEqual(state["orders"][0]["customer"], "Tara")
        self.assertIsNone(state["orders"][0]["courier"])
        self.assertEqual(state["couriers"][0]["status"], "free, delivered 0")

    def test_buttons_follow_the_order_state_and_finished_orders_go_last(self):
        finished = self.service.place_order("C1", "R1", [("Pizza", 1)])
        self.service.cancel(finished.id)
        assigned = self.service.place_order("C2", "R1", [("Cola", 1)])
        self.service.dispatch_order(assigned.id)
        waiting = self.service.place_order("C3", "R1", [("Salad", 1)])

        orders = self.api.state()["orders"]

        self.assertEqual([o["id"] for o in orders], [assigned.id, waiting.id, finished.id])
        self.assertEqual(actions_of(orders[0]), ["pick_up", "cancel"])
        self.assertEqual(actions_of(orders[1]), ["dispatch", "cancel"])
        self.assertEqual(actions_of(orders[2]), [])

    def test_place_order_reply_includes_observer_messages(self):
        reply = self.api.place_order(
            {"customer_id": "C1", "restaurant_id": "R1", "items": "Pizza*2, Cola"})

        self.assertTrue(reply["message"].startswith("Order #1 placed."))
        self.assertIn("[to Tara] Order #1 received. Total 22.00.", reply["messages"])

    def test_place_order_needs_every_field(self):
        with self.assertRaises(ValidationError):
            self.api.place_order({"customer_id": "C1", "restaurant_id": "R1", "items": " "})
        self.assertEqual(self.service.all_orders(), [])

    def test_order_actions(self):
        order = self.service.place_order("C1", "R1", [("Pizza", 1)])

        reply = self.api.order_action(order.id, "dispatch")
        self.assertTrue(reply["message"].startswith(f"Order #{order.id} dispatched to Marko."))

        with self.assertRaises(InvalidStateError):
            self.api.order_action(order.id, "deliver")  # not picked up yet
        with self.assertRaises(NotFoundError):
            self.api.order_action(order.id, "teleport")

    def test_dispatch_waiting_reports_nothing_to_do(self):
        self.assertEqual(self.api.dispatch_waiting()["message"], "No order could be dispatched.")


class StateActionsTestCase(unittest.TestCase):
    """state.actions must match the methods each state really allows."""

    METHOD_FOR_ACTION = {"dispatch": "assign", "pick_up": "pick_up",
                         "deliver": "deliver", "cancel": "cancel"}

    def test_listed_actions_are_exactly_the_allowed_ones(self):
        for state_class in (NewState, AssignedState, PickedUpState, DeliveredState, CancelledState):
            with self.subTest(state_class.__name__):
                allowed = {
                    action for action, method in self.METHOD_FOR_ACTION.items()
                    # A state allows an action by overriding the refusing base method.
                    if getattr(state_class, method) is not getattr(OrderState, method)
                }
                self.assertEqual(set(state_class.actions), allowed)
                self.assertEqual(state_class.is_final, not allowed)


class ParseItemsTestCase(unittest.TestCase):

    def test_parses_quantities_and_skips_empty_parts(self):
        self.assertEqual(parse_items("Pizza*2, Cola,, "), [("Pizza", 2), ("Cola", 1)])

    def test_bad_quantity_is_a_validation_error(self):
        with self.assertRaises(ValidationError):
            parse_items("Pizza*two")


class HttpTestCase(unittest.TestCase):
    """
    Real HTTP requests. The server handles each request on THIS thread (the
    one that owns the SQLite connection); only the client runs in a thread.
    """

    def setUp(self):
        self.app = load_sample_data(build_app(database=IN_MEMORY))
        self.addCleanup(self.app.close)
        self.server = create_server(self.app, port=0)
        self.addCleanup(self.server.server_close)
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def request(self, path, data=None, content_type="application/json"):
        """Send one request and return (status, content type, body)."""
        body = None if data is None else json.dumps(data).encode()
        request = urllib.request.Request(self.base + path, data=body)
        if body is not None:
            request.add_header("Content-Type", content_type)
        result = {}

        def client():
            try:
                with urllib.request.urlopen(request, timeout=5) as response:
                    result["answer"] = (response.status, response.headers["Content-Type"],
                                        response.read())
            except urllib.error.HTTPError as error:
                result["answer"] = (error.code, error.headers["Content-Type"], error.read())

        thread = threading.Thread(target=client)
        thread.start()
        self.server.handle_request()
        thread.join(timeout=5)
        return result["answer"]

    def test_serves_the_page(self):
        status, content_type, body = self.request("/")
        self.assertEqual(status, 200)
        self.assertTrue(content_type.startswith("text/html"))
        self.assertIn(b"<title>Food Delivery</title>", body)

    def test_place_order_then_state(self):
        status, _, body = self.request(
            "/api/orders", {"customer_id": "C2", "restaurant_id": "R1", "items": "Cola"})
        self.assertEqual(status, 200)
        self.assertIn("placed", json.loads(body)["message"])

        status, _, body = self.request("/api/state")
        self.assertEqual(json.loads(body)["orders"][0]["customer"], "Alice")

    def test_errors_become_json_with_matching_status(self):
        cases = [
            ("/api/orders/99/cancel", {}, "application/json", 404),
            ("/api/orders", {"customer_id": "C1", "restaurant_id": "R1", "items": "Burger"},
             "application/json", 400),
            ("/api/dispatch", {}, "text/plain", 415),
            ("/api/unknown", {}, "application/json", 404),
        ]
        for path, data, content_type, expected in cases:
            with self.subTest(path=path, content_type=content_type):
                status, _, body = self.request(path, data, content_type)
                self.assertEqual(status, expected)
                self.assertIn("error", json.loads(body))


if __name__ == "__main__":
    unittest.main()
