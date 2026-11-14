"""
STATE pattern - the life of an order.

An order is always in exactly ONE state:

    NEW --assign--> ASSIGNED --pick_up--> PICKED_UP --deliver--> DELIVERED
     |                 |
     +----cancel-------+------> CANCELLED

Each state is its own class. The order does not use big if/else blocks;
it simply forwards the action to its current state object, and that state
decides: "allowed -> move to next state" or "not allowed -> raise error".

The base class says "nothing is allowed". Each state only overrides the
actions that ARE allowed in that state.
"""

from delivery.common.errors import InvalidStateError


class OrderState:
    """Base state: every action is refused unless a subclass allows it."""

    # Text name shown to users, e.g. "NEW". Subclasses overwrite it.
    name = "BASE"

    # True for states where nothing more can happen.
    is_final = False

    def _refuse(self, action):
        """Helper that raises a clear error for a not-allowed action."""
        raise InvalidStateError(f"Cannot {action} an order that is {self.name}.")

    def assign(self, order, courier):
        """Give the order to a courier."""
        self._refuse("assign")

    def pick_up(self, order):
        """Courier takes the food from the restaurant."""
        self._refuse("pick up")

    def deliver(self, order):
        """Courier hands the food to the customer."""
        self._refuse("deliver")

    def cancel(self, order):
        """Stop the order."""
        self._refuse("cancel")

    def __repr__(self):
        return self.name


class NewState(OrderState):
    """Order was placed, no courier yet."""

    name = "NEW"

    def assign(self, order, courier):
        order.set_courier(courier)
        order.change_state(AssignedState(), "assigned")

    def cancel(self, order):
        order.change_state(CancelledState(), "cancelled")


class AssignedState(OrderState):
    """A courier is on the way to the restaurant."""

    name = "ASSIGNED"

    def pick_up(self, order):
        order.change_state(PickedUpState(), "picked_up")

    def cancel(self, order):
        order.change_state(CancelledState(), "cancelled")


class PickedUpState(OrderState):
    """The courier has the food and rides to the customer."""

    name = "PICKED_UP"

    def deliver(self, order):
        order.change_state(DeliveredState(), "delivered")


class DeliveredState(OrderState):
    """Food reached the customer. Final state."""

    name = "DELIVERED"
    is_final = True


class CancelledState(OrderState):
    """Order was stopped. Final state."""

    name = "CANCELLED"
    is_final = True
