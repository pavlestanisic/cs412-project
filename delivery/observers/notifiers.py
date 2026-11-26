"""
OBSERVER pattern - the concrete observers.

Each notifier listens to orders and reacts to events in its own way:

  * CustomerNotifier   -- writes friendly messages for the customer
  * RestaurantNotifier -- tells the kitchen what to do
  * EventLogObserver   -- writes every event into the log file

The notifiers do not really send SMS/e-mail. They keep the messages in a
list called `messages`; AppContext.take_messages() hands them to the console
or the web page to display.
"""

import logging

from delivery.common.observer import Observer

log = logging.getLogger(__name__)


class MessageNotifier(Observer):
    """Shared base for notifiers that collect text messages."""

    def __init__(self):
        self.messages = []  # every message this notifier "sent"

    def update(self, order, event):
        """Turn the event into a message (if this notifier cares about it)."""
        # Subject.notify calls this inherited method for both message notifiers.
        # Their make_message methods decide which events need a message.
        text = self.make_message(order, event)
        if text:  # None means "this event is not interesting for me"
            self.messages.append(text)

    def make_message(self, order, event):
        """Return message text, or None. Subclasses override this."""
        return None

    def clear(self):
        """Forget the collected messages."""
        self.messages.clear()


# Watches created, assigned, picked_up, delivered and cancelled events.
# Reads the emitting order to explain its progress to that order's customer.
# Messages are collected locally; this class does not send SMS or email.
class CustomerNotifier(MessageNotifier):
    """Messages for the person who ordered."""

    def make_message(self, order, event):
        name = order.customer.name
        if event == "created":
            return f"[to {name}] Order #{order.id} received. Total {order.total():.2f}."
        if event == "assigned":
            return (f"[to {name}] {order.courier.name} ({order.courier.vehicle}) will bring "
                    f"order #{order.id} in about {order.estimated_minutes()} min.")
        if event == "picked_up":
            return f"[to {name}] Order #{order.id} is on the way!"
        if event == "delivered":
            return f"[to {name}] Order #{order.id} delivered. Enjoy your meal!"
        if event == "cancelled":
            return f"[to {name}] Order #{order.id} was cancelled."
        return None


# Receives the same events, but produces messages only for created, assigned
# and cancelled: what to cook, who will collect it, and when to stop cooking.
# Pickup and delivery events return None and produce no kitchen message.
class RestaurantNotifier(MessageNotifier):
    """Messages for the restaurant kitchen."""

    def make_message(self, order, event):
        place = order.restaurant.name
        if event == "created":
            items = ", ".join(repr(line) for line in order.lines)
            return f"[to {place}] Please cook order #{order.id}: {items}."
        if event == "assigned":
            return f"[to {place}] {order.courier.name} will collect order #{order.id}."
        if event == "cancelled":
            return f"[to {place}] Stop cooking order #{order.id}, it was cancelled."
        return None


# Watches every event delivered to update, without filtering its name.
# One shared instance counts events across all attached orders. At startup the
# counts are read ONCE from the saved history (order_events); after that only
# newly committed events add to them. Restored events are never replayed, so
# nothing is counted twice. Each log entry identifies the order and its state.
class EventLogObserver(Observer):
    """Writes each event into the app log. Also counts events (for reports)."""

    def __init__(self, saved_counts=None):
        # event text -> how many times it happened, including earlier runs
        self.event_counts = dict(saved_counts or {})

    def update(self, order, event):
        self.event_counts[event] = self.event_counts.get(event, 0) + 1
        log.info("EVENT %-9s order=%s state=%s", event, order.id, order.state_name)
