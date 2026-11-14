"""
ABSTRACT FACTORY pattern - delivery options.

A delivery option ("standard" or "express") is a FAMILY of two objects
that must match each other:

  * a PriceCalculator  -- how much the delivery costs
  * a TimeEstimator    -- how long the delivery takes

`DeliveryOptionFactory` is the abstract factory: it promises to create both
products. `StandardDeliveryFactory` and `ExpressDeliveryFactory` are the
concrete factories. Because one factory creates the whole family, you can
never mix "express price" with "standard time" by mistake.
"""

from abc import ABC, abstractmethod

from delivery.common.errors import ValidationError

# ---------------------------------------------------------------------------
# Product 1: price calculators
# ---------------------------------------------------------------------------


class PriceCalculator(ABC):
    """Works out the delivery fee."""

    @abstractmethod
    def delivery_fee(self, distance_km):
        """Fee (money) for driving `distance_km` from restaurant to customer."""


class StandardPriceCalculator(PriceCalculator):
    """Standard: 2.00 base + 0.50 per km."""

    def delivery_fee(self, distance_km):
        return round(2.00 + 0.50 * distance_km, 2)


class ExpressPriceCalculator(PriceCalculator):
    """Express: 5.00 base + 1.00 per km."""

    def delivery_fee(self, distance_km):
        return round(5.00 + 1.00 * distance_km, 2)


# ---------------------------------------------------------------------------
# Product 2: time estimators
# ---------------------------------------------------------------------------


class TimeEstimator(ABC):
    """Works out how many minutes until the food arrives."""

    @abstractmethod
    def cooking_minutes(self):
        """How long the kitchen needs."""

    def estimate_minutes(self, travel_minutes):
        """Total time = cooking time + time on the road."""
        return self.cooking_minutes() + travel_minutes


class StandardTimeEstimator(TimeEstimator):
    """Standard orders wait in the normal kitchen queue: 20 minutes."""

    def cooking_minutes(self):
        return 20


class ExpressTimeEstimator(TimeEstimator):
    """Express orders jump the kitchen queue: 10 minutes."""

    def cooking_minutes(self):
        return 10


# ---------------------------------------------------------------------------
# The abstract factory and its concrete factories
# ---------------------------------------------------------------------------


class DeliveryOptionFactory(ABC):
    """Abstract factory: creates a matching price calculator + time estimator."""

    # Text name of the option, e.g. "standard". Subclasses overwrite it.
    name = "base"

    @abstractmethod
    def create_price_calculator(self):
        """Return a PriceCalculator for this option."""

    @abstractmethod
    def create_time_estimator(self):
        """Return a TimeEstimator for this option."""


class StandardDeliveryFactory(DeliveryOptionFactory):
    """Family of objects for standard (cheap, slower) delivery."""

    name = "standard"

    def create_price_calculator(self):
        return StandardPriceCalculator()

    def create_time_estimator(self):
        return StandardTimeEstimator()


class ExpressDeliveryFactory(DeliveryOptionFactory):
    """Family of objects for express (expensive, faster) delivery."""

    name = "express"

    def create_price_calculator(self):
        return ExpressPriceCalculator()

    def create_time_estimator(self):
        return ExpressTimeEstimator()


def get_delivery_factory(option_name):
    """Return the factory for 'standard' or 'express'."""
    factories = {
        "standard": StandardDeliveryFactory,
        "express": ExpressDeliveryFactory,
    }
    if option_name not in factories:
        raise ValidationError(f"Unknown delivery option '{option_name}'. Use one of {sorted(factories)}.")
    return factories[option_name]()
