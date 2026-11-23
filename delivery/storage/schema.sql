PRAGMA foreign_keys = ON;

CREATE TABLE customers (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL CHECK (length(trim(name)) > 0),
    address_x REAL NOT NULL,
    address_y REAL NOT NULL,
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1))
);

CREATE TABLE restaurants (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL CHECK (length(trim(name)) > 0),
    location_x REAL NOT NULL,
    location_y REAL NOT NULL,
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1))
);

CREATE TABLE menu_items (
    id INTEGER PRIMARY KEY,
    restaurant_id TEXT NOT NULL REFERENCES restaurants(id),
    name TEXT NOT NULL CHECK (length(trim(name)) > 0),
    price_cents INTEGER NOT NULL
        CHECK (typeof(price_cents) = 'integer' AND price_cents > 0),
    available INTEGER NOT NULL DEFAULT 1
        CHECK (available IN (0, 1)),
    UNIQUE (restaurant_id, name)
);

CREATE TABLE couriers (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL CHECK (length(trim(name)) > 0),
    vehicle TEXT NOT NULL
        CHECK (vehicle IN ('bike', 'car', 'walking')),
    location_x REAL NOT NULL,
    location_y REAL NOT NULL,
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1))
);

CREATE TABLE orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id TEXT NOT NULL REFERENCES customers(id),
    restaurant_id TEXT NOT NULL REFERENCES restaurants(id),
    courier_id TEXT REFERENCES couriers(id),

    state TEXT NOT NULL DEFAULT 'NEW'
        CHECK (
            state IN (
                'NEW', 'ASSIGNED', 'PICKED_UP',
                'DELIVERED', 'CANCELLED'
            )
        ),

    delivery_option TEXT NOT NULL
        CHECK (delivery_option IN ('standard', 'express')),

    delivery_x REAL NOT NULL,
    delivery_y REAL NOT NULL,

    delivery_fee_cents INTEGER NOT NULL
        CHECK (
            typeof(delivery_fee_cents) = 'integer'
            AND delivery_fee_cents >= 0
        ),

    note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CHECK (state != 'NEW' OR courier_id IS NULL),
    CHECK (
        state NOT IN ('ASSIGNED', 'PICKED_UP', 'DELIVERED')
        OR courier_id IS NOT NULL
    )
);

CREATE TABLE order_items (
    id INTEGER PRIMARY KEY,
    order_id INTEGER NOT NULL REFERENCES orders(id),
    menu_item_id INTEGER NOT NULL REFERENCES menu_items(id),

    dish_name TEXT NOT NULL,
    unit_price_cents INTEGER NOT NULL
        CHECK (
            typeof(unit_price_cents) = 'integer'
            AND unit_price_cents > 0
        ),
    quantity INTEGER NOT NULL
        CHECK (typeof(quantity) = 'integer' AND quantity > 0)
);

CREATE TABLE order_events (
    id INTEGER PRIMARY KEY,
    order_id INTEGER NOT NULL REFERENCES orders(id),
    event TEXT NOT NULL
        CHECK (
            event IN (
                'created', 'assigned', 'picked_up',
                'delivered', 'cancelled'
            )
        ),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX one_active_order_per_courier
ON orders(courier_id)
WHERE state IN ('ASSIGNED', 'PICKED_UP');

CREATE INDEX orders_by_customer ON orders(customer_id);
CREATE INDEX orders_by_state ON orders(state);
CREATE INDEX items_by_order ON order_items(order_id);
CREATE INDEX events_by_order ON order_events(order_id);