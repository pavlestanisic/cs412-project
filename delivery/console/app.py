"""
PRESENTATION LAYER - the text screen.

This layer only:
  * reads what the user typed,
  * calls a service,
  * prints the result.

It contains NO business rules. All rules live in the service/domain layers.

`output` and `input_func` are passed in (default: print / input).
"""

from delivery.common.errors import DispatchError


def parse_items(text):
    """
    Turn 'Pizza*2, Cola' into [('Pizza', 2), ('Cola', 1)].
    A missing '*number' means quantity 1.
    """
    items = []
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue  # ignore empty pieces like in "Pizza,,Cola"
        if "*" in part:
            name, quantity = part.rsplit("*", 1)
            items.append((name.strip(), int(quantity)))
        else:
            items.append((part, 1))
    return items


class ConsoleApp:
    """Text user interface on top of the service layer."""

    def __init__(self, app, output=print, input_func=input):
        self._app = app           # the AppContext from core.factory
        self._out = output
        self._ask = input_func

    # ----- small printing helpers -----------------------------------------

    def _title(self, text):
        """Print a section title."""
        self._out("")
        self._out(f"=== {text} ===")

    def _flush_messages(self):
        """Print every message the notifiers (observers) collected."""
        for message in self._app.take_messages():
            self._out("  " + message)

    def _try(self, action, *args):
        """Run a service call; print app errors instead of crashing."""
        try:
            result = action(*args)
        except (DispatchError, ValueError) as error:
            self._out(f"  ERROR: {error}")
            result = None
        self._flush_messages()
        return result

    # ----- screens --------------------------------------------------------

    def show_restaurants(self):
        """Print every restaurant with its menu."""
        self._title("Restaurants")
        for restaurant in self._app.catalog.restaurants():
            self._out(f"{restaurant.id} {restaurant.name} at {restaurant.location}")
            for item in restaurant.menu_items():
                self._out(f"    {item.name:<12} {item.price:6.2f}")

    def show_orders(self):
        """Print every order with its state and price."""
        self._title("Orders")
        for order in self._app.order_service.all_orders():
            courier = order.courier.name if order.courier else "-"
            self._out(f"#{order.id} {order.customer.name:<6} {order.restaurant.name:<12} "
                      f"{order.delivery_option:<8} {order.state_name:<10} "
                      f"courier={courier:<7} total={order.total():.2f}")

    def show_couriers(self):
        """Print every courier and whether they are busy."""
        self._title("Couriers")
        for courier in self._app.catalog.couriers():
            status = "free" if courier.is_free else f"busy with #{courier.current_order.id}"
            self._out(f"{courier.id} {courier.name:<7} {courier.vehicle:<8} at {courier.location} "
                      f"{status:<14} delivered={courier.delivered_count}")

    def show_health(self):
        """Print the runtime health check result."""
        self._title("Health check")
        problems = self._app.health.problems()
        if not problems:
            self._out("OK - all rules hold.")
        for problem in problems:
            self._out("PROBLEM: " + problem)
        return not problems

    def dispatch_waiting(self):
        """Dispatch all NEW orders and print who got what."""
        matched = self._try(self._app.order_service.dispatch_waiting_orders) or []
        if not matched:
            self._out("  No order could be dispatched.")
        return matched

    # ----- the scripted demo ----------------------------------------------

    def run_demo(self):
        """
        Play a fixed story that touches every feature.
        Returns True if the final health check passed.
        """
        service = self._app.order_service
        self._out(f"Food delivery dispatch demo (dispatcher: {service.dispatcher.name})")
        self.show_restaurants()

        self._title("Placing orders")
        self._try(service.place_order, "C1", "R1", [("Pizza", 2), ("Cola", 1)], "standard", "ring twice")
        self._try(service.place_order, "C2", "R2", [("Sushi Roll", 1)], "express")
        self._try(service.place_order, "C3", "R1", [("Salad", 1)], "standard")
        self._try(service.place_order, "C4", "R2", [("Miso Soup", 2)], "standard")
        self._out("Trying a dish that does not exist:")
        self._try(service.place_order, "C1", "R1", [("Burger", 1)], "standard")

        self._title("Dispatching (3 couriers, 4 orders)")
        self.dispatch_waiting()
        self.show_couriers()

        self._title("Order #1 is picked up and delivered")
        self._try(service.pick_up, 1)
        self._try(service.deliver, 1)

        self._title("A courier is free again - dispatch the waiting order")
        self.dispatch_waiting()

        self._title("Maja cancels order #3")
        self._try(service.cancel, 3)

        self._title("Trying to deliver order #2 before pick up")
        self._try(service.deliver, 2)

        self._title("Finishing the rest")
        for order_id in (2, 4):
            self._try(service.pick_up, order_id)
            self._try(service.deliver, order_id)

        self.show_orders()
        self.show_couriers()

        self._title("Event counts")
        for event, count in sorted(self._app.event_log.event_counts.items()):
            self._out(f"{event:<10} {count}")

        return self.show_health()

    # ----- interactive menu -----------------------------------------------

    MENU = """
1) Show restaurants      2) Place order        3) Dispatch waiting orders
4) Pick up order         5) Deliver order      6) Cancel order
7) Show orders           8) Show couriers      9) Health check
0) Quit"""

    def run_menu(self):
        """Simple loop: show menu, read a choice, run it, repeat until '0'."""
        service = self._app.order_service
        while True:
            self._out(self.MENU)
            choice = self._ask("Choose: ").strip()

            if choice == "0":
                self._out("Bye!")
                return
            if choice == "1":
                self.show_restaurants()
            elif choice == "2":
                customer_id = self._ask("Customer id (e.g. C1): ").strip()
                restaurant_id = self._ask("Restaurant id (e.g. R1): ").strip()
                items_text = self._ask("Items (e.g. Pizza*2, Cola): ")
                delivery = self._ask("Delivery (standard/express): ").strip() or "standard"
                self._try(lambda: service.place_order(customer_id, restaurant_id,
                                                      parse_items(items_text), delivery))
            elif choice == "3":
                self.dispatch_waiting()
            elif choice in ("4", "5", "6"):
                actions = {"4": service.pick_up, "5": service.deliver, "6": service.cancel}
                self._try(lambda: actions[choice](int(self._ask("Order number: "))))
            elif choice == "7":
                self.show_orders()
            elif choice == "8":
                self.show_couriers()
            elif choice == "9":
                self.show_health()
            else:
                self._out(f"Unknown choice '{choice}'.")
