"""
WEB ADAPTER - the browser page (index.html) on top of the service layer.

Like the console, this layer only:
  * reads what the user sent,
  * calls a service,
  * returns the result (as JSON).
It contains NO business rules. Which buttons an order gets comes from the
order's STATE object (state.actions), not from rules written here.

Two parts:
  * WebApi      -- turns service calls into plain dictionaries (no HTTP here,
                   so it is easy to test),
  * make_handler -- the small HTTP layer that routes URLs to WebApi.

The server is deliberately single-threaded (HTTPServer, not
ThreadingHTTPServer): the app has one SQLite connection and one shared set of
loaded objects, and neither may be used by two threads at the same time.

Endpoints used by index.html:
  GET  /                              the page
  GET  /api/state                     everything the page shows
  POST /api/orders                    place an order
  POST /api/orders/<id>/<action>      dispatch / pick_up / deliver / cancel
  POST /api/dispatch                  dispatch all waiting orders
"""

import json
import logging
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from delivery.common.errors import DispatchError, NotFoundError, ValidationError
from delivery.common.item_text import parse_items

log = logging.getLogger(__name__)

PAGE_PATH = Path(__file__).resolve().parent / "index.html"

# Button text for each action name a state can offer.
ACTION_LABELS = {
    "dispatch": "Dispatch",
    "pick_up": "Pick up",
    "deliver": "Deliver",
    "cancel": "Cancel",
}

# Refuse request bodies larger than this; the page only sends tiny forms.
MAX_BODY_BYTES = 64 * 1024


class WebApi:
    """Answers the page's requests using the application's services."""

    def __init__(self, app):
        self._app = app
        service = app.order_service
        # Action name (from state.actions) -> function(order_id) -> summary text.
        self._order_actions = {
            "dispatch": self._dispatch_one,
            "pick_up": self._simple_action(service.pick_up, "picked up"),
            "deliver": self._simple_action(service.deliver, "delivered"),
            "cancel": self._simple_action(service.cancel, "cancelled"),
        }

    # ----- reading --------------------------------------------------------

    def state(self):
        """Everything the page displays, as plain data."""
        catalog = self._app.catalog
        # Open orders first (they need attention), finished ones below.
        orders = sorted(
            self._app.order_service.all_orders(),
            key=lambda order: (order.state.is_final, order.id),
        )
        return {
            "customers": [
                {"id": customer.id, "name": customer.name}
                for customer in catalog.customers()
            ],
            "restaurants": [
                {
                    "id": restaurant.id,
                    "name": restaurant.name,
                    "menu": [
                        {"name": item.name, "price": item.price}
                        for item in restaurant.menu_items()
                    ],
                }
                for restaurant in catalog.restaurants()
            ],
            "orders": [self._order_data(order) for order in orders],
            "couriers": [self._courier_data(courier) for courier in catalog.couriers()],
        }

    @staticmethod
    def _order_data(order):
        return {
            "id": order.id,
            "customer": order.customer.name,
            "state": order.state_name,
            "courier": order.courier.name if order.courier else None,
            "total": order.total(),
            # The STATE pattern decides which buttons exist.
            "actions": [
                {"name": name, "label": ACTION_LABELS[name]}
                for name in order.state.actions
            ],
        }

    @staticmethod
    def _courier_data(courier):
        if courier.is_free:
            status = "free"
        else:
            status = f"busy with #{courier.current_order.id}"
        return {
            "id": courier.id,
            "name": courier.name,
            "vehicle": courier.vehicle,
            "status": f"{status}, delivered {courier.delivered_count}",
        }

    # ----- changing -------------------------------------------------------

    def place_order(self, data):
        """Place an order from the page's form fields."""
        order = self._app.order_service.place_order(
            self._required_text(data, "customer_id"),
            self._required_text(data, "restaurant_id"),
            parse_items(self._required_text(data, "items")),
            data.get("delivery") or "standard",
        )
        return self._reply(f"Order #{order.id} placed.")

    def order_action(self, order_id, action):
        """Run one action (e.g. 'pick_up') on one order."""
        call = self._order_actions.get(action)
        if call is None:
            raise NotFoundError(f"Unknown action '{action}'.")
        # The service and the order's state check whether it is allowed.
        summary = call(order_id)
        return self._reply(summary)

    def dispatch_waiting(self):
        """Dispatch every waiting order that a free courier can take."""
        matched = self._app.order_service.dispatch_waiting_orders()
        if not matched:
            return self._reply("No order could be dispatched.")
        return self._reply(f"Dispatched {len(matched)} order(s).")

    @staticmethod
    def _simple_action(call, done):
        """Wrap a service call so it reports e.g. 'Order #3 cancelled.'"""
        def run(order_id):
            call(order_id)
            return f"Order #{order_id} {done}."
        return run

    def _dispatch_one(self, order_id):
        courier = self._app.order_service.dispatch_order(order_id)
        if courier is None:
            return f"No free courier; order #{order_id} waits."
        return f"Order #{order_id} dispatched to {courier.name}."

    def _reply(self, summary):
        """A success reply: a short summary plus the observers' messages."""
        messages = self._app.take_messages()
        return {
            "message": " · ".join([summary] + messages),
            "messages": messages,
        }

    @staticmethod
    def _required_text(data, field):
        value = data.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValidationError(f"Field '{field}' is required.")
        return value.strip()


def make_handler(api):
    """Create the HTTP request handler class that serves `api`."""

    class Handler(BaseHTTPRequestHandler):

        def do_GET(self):
            if self.path == "/":
                self._send(HTTPStatus.OK, PAGE_PATH.read_bytes(), "text/html; charset=utf-8")
            elif self.path == "/api/state":
                self._answer(api.state)
            else:
                self._send_error(HTTPStatus.NOT_FOUND, "Not found.")

        def do_POST(self):
            # Only accept JSON. A form on another website cannot send JSON to
            # this server without the browser asking permission first, so this
            # also stops other sites from placing orders through your browser.
            content_type = self.headers.get("Content-Type", "")
            if content_type.split(";")[0].strip() != "application/json":
                self._send_error(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, "Send JSON.")
                return

            try:
                data = self._read_json()
            except ValueError as error:
                self._send_error(HTTPStatus.BAD_REQUEST, str(error))
                return

            parts = self.path.strip("/").split("/")
            if parts == ["api", "orders"]:
                self._answer(api.place_order, data)
            elif parts == ["api", "dispatch"]:
                self._answer(api.dispatch_waiting)
            elif len(parts) == 4 and parts[:2] == ["api", "orders"] and parts[2].isdigit():
                self._answer(api.order_action, int(parts[2]), parts[3])
            else:
                self._send_error(HTTPStatus.NOT_FOUND, "Not found.")

        # ----- helpers ----------------------------------------------------

        def _answer(self, call, *args):
            """Run an API call and turn its result or error into a response."""
            try:
                result = call(*args)
            except NotFoundError as error:
                self._send_error(HTTPStatus.NOT_FOUND, str(error))
            except DispatchError as error:
                self._send_error(HTTPStatus.BAD_REQUEST, str(error))
            except Exception:
                log.exception("Web request failed: %s %s", self.command, self.path)
                self._send_error(HTTPStatus.INTERNAL_SERVER_ERROR,
                                 "Internal error; see the application log.")
            else:
                self._send_json(HTTPStatus.OK, result)

        def _read_json(self):
            length = int(self.headers.get("Content-Length") or 0)
            if length > MAX_BODY_BYTES:
                raise ValueError("Request is too large.")
            body = self.rfile.read(length) if length else b"{}"
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                raise ValueError("Request body is not valid JSON.") from None
            if not isinstance(data, dict):
                raise ValueError("Request body must be a JSON object.")
            return data

        def _send_error(self, status, text):
            self._send_json(status, {"error": text})

        def _send_json(self, status, data):
            self._send(status, json.dumps(data).encode("utf-8"), "application/json")

        def _send(self, status, body, content_type):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format, *args):
            # Send the server's access log to our log file, not to stderr.
            log.debug("%s - %s", self.address_string(), format % args)

    return Handler


def create_server(app, host="127.0.0.1", port=8000):
    """Build the HTTP server. Port 0 picks any free port (used by tests)."""
    return HTTPServer((host, port), make_handler(WebApi(app)))


def serve(app, host="127.0.0.1", port=8000, output=print):
    """Serve the page until Ctrl+C."""
    server = create_server(app, host, port)
    url = f"http://{host}:{server.server_port}/"
    log.info("Web page at %s", url)
    output(f"Open {url} in your browser. Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        output("\nStopping the web server.")
    finally:
        server.server_close()
