"""
Location on a simple city grid.

The city is a grid of streets. A point is (x, y) in kilometers.
Distance is the "taxi" distance: how many km you drive along streets.
"""


class Location:
    """A point on the city grid."""

    def __init__(self, x, y):
        # Store the coordinates. Leading underscore = "please do not change
        # from outside" (encapsulation). Read them with the properties below.
        self._x = x
        self._y = y

    @property
    def x(self):
        """Horizontal position in km."""
        return self._x

    @property
    def y(self):
        """Vertical position in km."""
        return self._y

    def distance_to(self, other):
        """Street distance (km) from this point to another point."""
        return abs(self._x - other.x) + abs(self._y - other.y)

    def __eq__(self, other):
        """Two locations are equal when both coordinates are equal."""
        if not isinstance(other, Location):
            return NotImplemented
        return self._x == other.x and self._y == other.y

    def __hash__(self):
        """Needed because we defined __eq__ (lets Location go into sets)."""
        return hash((self._x, self._y))

    def __repr__(self):
        """Readable text like '(2, 3)'."""
        return f"({self._x}, {self._y})"
