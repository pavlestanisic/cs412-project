"""
Wiring - creates every object of the app and connects the layers.

This composition root owns the database connection, observers, dispatch
policy and services. The console consumes the resulting context; common
domain code stays independent.

Startup = restoration: the saved customers, restaurants, couriers and orders
are loaded once into one shared LoadedData. Services read those objects and
write every change back through the SQL repositories.
"""

from delivery.core.catalog_service import CatalogService
from delivery.core.order_service import OrderService
from delivery.dispatch.strategies import get_dispatcher
from delivery.observers.notifiers import CustomerNotifier, EventLogObserver, RestaurantNotifier
from delivery.reliability.health_check import HealthCheck
from delivery.storage.data_loader import DataLoader
from delivery.storage.database import DATABASE_PATH, connect, initialize_database
from delivery.storage.order_repository import OrderRepository
from delivery.storage.transaction_manager import TransactionManager


class AppContext:
    """A bag that holds every connected part of one running app."""

    def __init__(self, dispatcher_name="nearest", database=DATABASE_PATH):
        self.connection = connect(database)
        try:
            self._build(dispatcher_name)
        except Exception:
            self.connection.close()
            raise

    def _build(self, dispatcher_name):
        initialize_database(self.connection)
        self.transactions = TransactionManager(self.connection)

        # --- restore everything that was saved, in one consistent read ---
        with self.transactions.transaction() as connection:
            self.data = DataLoader(connection).load()
            saved_event_counts = OrderRepository(connection).event_counts()

        # --- observers that every order will report to ---
        self.customer_notifier = CustomerNotifier()
        self.restaurant_notifier = RestaurantNotifier()
        self.event_log = EventLogObserver(saved_event_counts)

        # --- service layer ---
        self.catalog = CatalogService(self.data, self.transactions)
        self.order_service = OrderService(
            self.data, self.transactions,
            dispatcher=get_dispatcher(dispatcher_name),
            observers=[self.customer_notifier, self.restaurant_notifier, self.event_log],
        )
        self.health = HealthCheck(self.order_service.all_orders, self.catalog.couriers)

    def take_messages(self):
        """Return all new notifier messages (customer first) and clear them."""
        messages = self.customer_notifier.messages + self.restaurant_notifier.messages
        self.customer_notifier.clear()
        self.restaurant_notifier.clear()
        return messages

    def close(self):
        """Close the database connection. The app cannot be used afterwards."""
        self.connection.close()


def build_app(dispatcher_name="nearest", database=DATABASE_PATH):
    """
    Create a fully connected app restored from `database`.

    database -- path of the SQLite file, or ":memory:" for a throwaway
                database (used by the demo and the tests).
    """
    return AppContext(dispatcher_name=dispatcher_name, database=database)
