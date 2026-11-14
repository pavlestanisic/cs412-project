"""
RUNTIME CHECKS - rules that must ALWAYS be true while the app runs.

`HealthCheck.problems()` looks at all orders and couriers and returns a list
of broken rules (an empty list means "all good"). The app runs it at the end
of the demo and when the operator selects the health-check menu option.

Rules:
  1. A busy courier's order must say that courier is the one carrying it.
  2. A busy courier's order must be ASSIGNED or PICKED_UP.
  3. Every ASSIGNED / PICKED_UP order must have a courier who carries it.
  4. A NEW order must not have a courier yet.
  5. Money values must never be negative.
"""

import logging

log = logging.getLogger(__name__)

# States in which a courier is holding the order.
ACTIVE_STATES = ("ASSIGNED", "PICKED_UP")


class HealthCheck:
    """Checks the rules above against the stored data."""

    def __init__(self, orders, couriers):
        self._orders = orders
        self._couriers = couriers

    def problems(self):
        """Return a list of text descriptions of every broken rule."""
        found = []

        for courier in self._couriers.all():
            order = courier.current_order
            if order is None:
                continue
            if order.courier is not courier:                                   # rule 1
                found.append(f"Courier {courier.id} holds order {order.id} but the order names someone else.")
            if order.state_name not in ACTIVE_STATES:                          # rule 2
                found.append(f"Courier {courier.id} holds order {order.id} which is {order.state_name}.")

        for order in self._orders.all():
            if order.state_name in ACTIVE_STATES:                              # rule 3
                if order.courier is None or order.courier.current_order is not order:
                    found.append(f"Order {order.id} is {order.state_name} but no courier carries it.")
            if order.state_name == "NEW" and order.courier is not None:        # rule 4
                found.append(f"Order {order.id} is NEW but already has a courier.")
            if order.food_total() < 0 or order.delivery_fee() < 0:             # rule 5
                found.append(f"Order {order.id} has a negative price.")

        for text in found:
            log.error("HEALTH CHECK: %s", text)
        return found

    def is_healthy(self):
        """True when no rule is broken."""
        return not self.problems()
