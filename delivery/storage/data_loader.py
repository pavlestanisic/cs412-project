"""
RESTORATION - turning the saved rows back into connected Python objects.

Runs at startup and after a failed change. Loading only rebuilds objects;
it never announces events, so observers do not hear old news again.
"""

from delivery.storage.customer_repository import CustomerRepository
from delivery.storage.restaurant_repository import RestaurantRepository
from delivery.storage.courier_repository import CourierRepository
from delivery.storage.order_repository import OrderRepository


class LoadedData:
    """
    Hold the connected objects loaded from the database.

    The application keeps ONE LoadedData for its whole run. CatalogService,
    OrderService and HealthCheck all read the same dictionaries, so a courier
    and the order it carries are the same Python objects everywhere.
    """

    def __init__(self, customers, restaurants, couriers, orders):
        self.customers = customers
        self.restaurants = restaurants
        self.couriers = couriers
        self.orders = orders

    def replace_with(self, other):
        """
        Swap in freshly loaded objects, keeping these dictionary objects.

        Used after a failed transaction: the database rolled back, but the
        Python objects did not, so they are thrown away and loaded again.
        """
        for name in ("customers", "restaurants", "couriers", "orders"):
            mine = getattr(self, name)
            mine.clear()
            mine.update(getattr(other, name))


class DataLoader:
    """Load related objects using one shared database connection."""

    def __init__(self, connection):
        self.connection = connection

    def load(self):
        """
        Load everything and return a LoadedData.

        Customers, restaurants and couriers come first, because each order
        is linked to the very same objects (not to copies of them).
        """
        customer_repository = CustomerRepository(self.connection)
        restaurant_repository = RestaurantRepository(self.connection)
        courier_repository = CourierRepository(self.connection)
        order_repository = OrderRepository(self.connection)

        customers = self._by_id(customer_repository.all())
        restaurants = self._by_id(restaurant_repository.all())
        couriers = self._by_id(courier_repository.all())

        orders = order_repository.load_all(
            customers,
            restaurants,
            couriers,
        )

        return LoadedData(
            customers,
            restaurants,
            couriers,
            orders,
        )

    @staticmethod
    def _by_id(objects):
        """Arrange objects by ID so relationships can find them."""
        objects_by_id = {}

        for obj in objects:
            objects_by_id[obj.id] = obj

        return objects_by_id
