from delivery.common.errors import NotFoundError 


"""Populate a supplied application using its catalog service."""

def load_sample_data(app):
    """Fill the app with a small fixed city so the demo always looks the same."""
    catalog = app.catalog

    sample_restaurants = [
    (
        "R1",
        "Pizza Place",
        2,
        2,
        {"Pizza": 8.50, "Cola": 2.00, "Salad": 6.00},
    ),
    (
        "R2",
        "Sushi Bar",
        7,
        6,
        {"Sushi Roll": 12.00, "Miso Soup": 4.00},
    ),
    (
        "R3",
        "Hamburger Joint",
        14,
        10,
        {"Hamburger": 10.00, "Fries": 3.00},
    ),
]
    for restaurant_id, name, x, y, dishes in sample_restaurants:
        try:
            app.restaurants.get(restaurant_id)
        except NotFoundError:
            catalog.add_restaurant(
                restaurant_id, name, x, y, dishes
        )

    sample_customers = [
        ("C1", "Tara", 1, 1),  
        ("C2", "Alice", 5, 5),    
        ("C3", "Xhoi", 9, 9),
        ("C3", "Dusan", 9, 9),
    ]

    for customer_id, name, x, y in sample_customers:
        try:
            app.customers.get(customer_id)
        except NotFoundError:
            catalog.add_customer(customer_id, name, x, y)

    catalog.hire_courier("bike", "K1", "Marko", 1, 1)
    catalog.hire_courier("car", "K2", "Jelena", 8, 8)
    catalog.hire_courier("walking", "K3", "Ivan", 4, 4)
    return app
