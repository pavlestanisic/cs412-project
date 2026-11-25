"""
OBSERVER pattern - the two base classes.

* `Subject`  -- something that changes (here: an Order).
* `Observer` -- something that wants to hear about the changes
                (here: notifiers that message the customer, restaurant, ...).

The subject keeps a list of observers. When it changes it calls
`observer.update(...)` on each of them. The subject does not know what the
observers do - it only knows they have an `update` method.
"""

import logging
from abc import ABC, abstractmethod

log = logging.getLogger(__name__)


# Observers do not watch variables or run background checks. They react only
# when an order explicitly calls notify(event), which calls their update method.
class Observer(ABC):
    """Anything that wants to be told about order events."""

    @abstractmethod
    def update(self, order, event):
        """
        Called by the subject.

        order -- the Order that changed.
        event -- short text, e.g. "created", "assigned", "delivered".
        """


class Subject:
    """Something that can be observed."""

    def __init__(self):
        self._observers = []  # list of Observer objects

    # OrderService attaches the application's shared notifier instances to each
    # new order. Each order maintains its own list of subscriptions.
    def attach(self, observer):
        """Start sending events to `observer` (added only once)."""
        if observer not in self._observers:
            self._observers.append(observer)

    def detach(self, observer):
        """Stop sending events to `observer` (ignored if not attached)."""
        if observer in self._observers:
            self._observers.remove(observer)

    def notify(self, event):
        """Tell every attached observer that `event` happened."""
        # Take a snapshot of the recipients so attach/detach during a callback
        # does not change this event's recipient list. New subscriptions apply
        # to later notifications; a detached recipient may still get this one.
        for observer in list(self._observers):
            # Here self is the Order that emitted the event. Pass the live order
            # so the observer can read its customer, courier, items and state.
            # Callbacks run immediately, one after another. A failing observer
            # is logged and skipped, so it cannot stop the others or undo the
            # change that caused the event. There is no retry.
            try:
                observer.update(self, event)
            except Exception:
                log.exception(
                    "Observer %s failed on event %s from %r",
                    type(observer).__name__,
                    event,
                    self,
                )

    @property
    def observers(self):
        """A copy of the attached observers (read only)."""
        return list(self._observers)
