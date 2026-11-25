"""Reading the items a user typed, shared by the console and the web page."""

from delivery.common.errors import ValidationError


def parse_items(text):
    """
    Turn 'Pizza*2, Cola' into [('Pizza', 2), ('Cola', 1)].
    A missing '*number' means quantity 1.
    """
    items = []
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue  # ignore empty pieces like in "Pizza,,Cola"
        if "*" in part:
            name, quantity = part.rsplit("*", 1)
            try:
                items.append((name.strip(), int(quantity)))
            except ValueError:
                raise ValidationError(
                    f"Quantity in '{part}' must be a whole number."
                ) from None
        else:
            items.append((part, 1))
    return items
