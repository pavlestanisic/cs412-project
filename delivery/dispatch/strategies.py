"""
TEMPLATE METHOD pattern - choosing a courier for an order.

`Dispatcher.dispatch()` is the template method. It fixes the ORDER of the
steps, which is the same for every dispatcher:

    1. find_candidates()   -> which couriers could take the order
    2. choose_courier()    -> pick ONE of them         <- subclasses decide
    3. assign()            -> connect order and courier

Only step 2 is abstract. `NearestCourierDispatcher` and
`FastestCourierDispatcher` fill it in differently; steps 1 and 3 are shared.
"""

import logging
from abc import ABC, abstractmethod

log = logging.getLogger(__name__)


class Dispatcher(ABC):
    """Base class that holds the dispatch algorithm skeleton."""

    # Text name for logs/output. Subclasses overwrite it.
    name = "base"

    # AI — previous implementation, kept for comparison. Had a hard time understanding. Prompt will be pasted tomorrow into a new md file.
    # dispatch filters free couriers, selects one through the subclass policy,
    # assigns the order, logs the result, and returns the selected courier.
    # find_candidates uses a list comprehension to collect free couriers.
    # def dispatch(self, order, couriers):
    #     """
    #     THE template method. Do not override - override the steps instead.
    #
    #     Returns the chosen courier, or None when nobody is free.
    #     """
    #     candidates = self.find_candidates(couriers)
    #     if not candidates:
    #         log.warning("Order %s: no free courier, it waits.", order.id)
    #         return None
    #     courier = self.choose_courier(order, candidates)
    #     self.assign(order, courier)
    #     log.info("Order %s dispatched to %s by %s dispatcher", order.id, courier.id, self.name)
    #     return courier
    #
    # def find_candidates(self, couriers):
    #     """Step 1 (shared): only free couriers can take an order."""
    #     return [courier for courier in couriers if courier.is_free]
    #

    def dispatch(self, order, couriers):
        """Assign an available courier, or leave the order waiting."""
        available_couriers = self.find_candidates(couriers)

        if not available_couriers:
            log.warning("Order %s: no free courier, it waits.", order.id)
            return None

        selected_courier = self.choose_courier(order, available_couriers)
        self.assign(order, selected_courier)

        log.info(
            "Order %s dispatched to %s by %s dispatcher",
            order.id,
            selected_courier.id,
            self.name,
        )
        return selected_courier

    def find_candidates(self, couriers):
        """Collect couriers who are not carrying an order."""
        available_couriers = []

        for courier in couriers:
            if courier.is_free:
                available_couriers.append(courier)

        return available_couriers

    @abstractmethod
    def choose_courier(self, order, candidates):
        """Step 2 (different per subclass): pick one courier from the list."""

    def assign(self, order, courier):
        """Step 3 (shared): update the order first (state check), then courier."""
        order.assign(courier)      # raises if the order is not NEW
        courier.take_order(order)


class NearestCourierDispatcher(Dispatcher):
    """Pick the courier who is closest to the restaurant."""

    name = "nearest"

    # AI — previous implementation, kept for comparison. Had a hard time understanding. Prompt will be pasted tomorrow into a new md file.
    # The lambda calculates each courier's distance to the restaurant.
    # min() returns the closest courier and keeps the first courier on a tie.
    # def choose_courier(self, order, candidates):
    #     # min() keeps the FIRST courier when distances are equal -> stable.
    #     return min(candidates, key=lambda c: c.location.distance_to(order.restaurant.location))

    def distance_to_restaurant(self, courier, order):
        """Calculate the grid distance from a courier to this restaurant."""
        return courier.location.distance_to(order.restaurant.location)

    def choose_courier(self, order, candidates):
        """Compare distances and return the closest available courier."""
        if not candidates:
            raise ValueError("Cannot choose a courier from an empty candidate list.")

        closest_courier = candidates[0]
        shortest_distance = self.distance_to_restaurant(closest_courier, order)

        for courier in candidates[1:]:
            distance = self.distance_to_restaurant(courier, order)
            # An equal distance leaves the earlier courier selected.
            if distance < shortest_distance:
                closest_courier = courier
                shortest_distance = distance

        return closest_courier


class FastestCourierDispatcher(Dispatcher):
    """Pick the courier whose food would arrive soonest (looks at speed too)."""

    name = "fastest"

    # AI — previous implementation, kept for comparison. Had a hard time understanding. Prompt will be pasted tomorrow into a new md file.
    # The lambda calculates each courier's estimated delivery time.
    # min() returns the courier with the lowest estimate, keeping the first tie.
    # def choose_courier(self, order, candidates):
    #     return min(candidates, key=lambda c: order.estimated_minutes(c))

    def choose_courier(self, order, candidates):
        """Compare arrival estimates and return the quickest courier."""
        if not candidates:
            raise ValueError("Cannot choose a courier from an empty candidate list.")

        fastest_courier = candidates[0]
        shortest_time = order.estimated_minutes(fastest_courier)

        for courier in candidates[1:]:
            estimated_time = order.estimated_minutes(courier)
            # An equal estimate leaves the earlier courier selected.
            if estimated_time < shortest_time:
                fastest_courier = courier
                shortest_time = estimated_time

        return fastest_courier


def get_dispatcher(name):
    """Return a dispatcher by name: 'nearest' or 'fastest'."""
    if name == "nearest":
        return NearestCourierDispatcher()
    if name == "fastest":
        return FastestCourierDispatcher()
    raise ValueError(f"Unknown dispatcher '{name}'. Use 'nearest' or 'fastest'.")
