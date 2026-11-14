"""
Wiring - creates every object of the app and connects the layers.

This composition root owns repositories, observers, dispatch policy and services.
The console consumes the resulting context; common domain code stays independent.

"""

from delivery.storage.repositories import (CourierRepository, CustomerRepository,
                                   OrderRepository, RestaurantRepository)
from delivery.core.catalog_service import CatalogService
from delivery.dispatch.strategies import get_dispatcher
from delivery.reliability.health_check import HealthCheck
from delivery.observers.notifiers import CustomerNotifier, EventLogObserver, RestaurantNotifier
from delivery.core.order_service import OrderService


class AppContext:
    """A bag that holds every connected part of one running app."""

    def __init__(self, dispatcher_name="nearest"):
        # --- data layer ---
        self.customers = CustomerRepository()
        self.restaurants = RestaurantRepository()
        self.couriers = CourierRepository()
        self.orders = OrderRepository()

        # --- observers that every order will report to ---
        self.customer_notifier = CustomerNotifier()
        self.restaurant_notifier = RestaurantNotifier()
        self.event_log = EventLogObserver()

        # --- service layer ---
        self.catalog = CatalogService(self.customers, self.restaurants, self.couriers)
        self.order_service = OrderService(
            self.orders, self.customers, self.restaurants, self.couriers,
            dispatcher=get_dispatcher(dispatcher_name),
            observers=[self.customer_notifier, self.restaurant_notifier, self.event_log],
        )
        self.health = HealthCheck(self.orders, self.couriers)

    def take_messages(self):
        """Return all new notifier messages (customer first) and clear them."""
        messages = self.customer_notifier.messages + self.restaurant_notifier.messages
        self.customer_notifier.clear()
        self.restaurant_notifier.clear()
        return messages


def build_app(dispatcher_name="nearest"):
    """Create a fresh, empty, fully connected app."""
    return AppContext(dispatcher_name)


