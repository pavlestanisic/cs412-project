# Food Delivery Dispatch

A console application for placing food orders, assigning couriers, and recording
pickup and delivery. Requires **Python 3.10 or later** and uses only Python's
standard library. No additional packages are needed.

## Start the program

Open a terminal and run:

```bash
cd /home/stanisicp/food_delivery_dispatch/food_delivery_restructured
python3 main.py --menu
```

If you have moved the project, change into the folder containing `main.py` instead.

Wait until the application displays `Choose:` before entering a menu number.
Typing `2` at the terminal's normal shell prompt will produce `command not found`.

## Terminal commands

Run these commands from the project folder:

| Command | What it does |
| --- | --- |
| `python3 main.py --menu` | Opens the interactive menu; assigns the nearest free courier. |
| `python3 main.py --menu --dispatcher nearest` | Explicitly selects nearest-courier assignment. |
| `python3 main.py --menu --dispatcher fastest` | Assigns couriers by estimated arrival time. |
| `python3 main.py --web` | Serves the web page at http://127.0.0.1:8000/ (Ctrl+C stops it). |
| `python3 main.py --web --port 8080` | Serves the web page on another port. |
| `python3 main.py` | Runs a scripted demonstration and exits. |
| `python3 main.py --dispatcher fastest` | Runs the demonstration using fastest-courier assignment. |
| `python3 -m delivery --menu` | Opens the same interactive menu through the package launcher. |
| `python3 main.py --help` | Lists available command-line options. |
| `python3 main.py --menu --log-console` | Also displays application logs in the terminal. |
| `python3 main.py --menu --log-level DEBUG --log-console` | Includes detailed logs in the file and terminal. |
| `python3 main.py --menu --log-file /tmp/food-delivery.log` | Writes logs to the specified file. |
| `python3 -m unittest discover -s tests/unit -v` | Run unit tests

**Include `--menu` to operate the app yourself.** Without it, the demo runs and
returns you to the terminal. The menu and the web page save their work in `data/delivery.db` and
continues where the previous run stopped; the demo always starts empty.

## Menu commands

At `Choose:`, type a number and press Enter. These are inputs to the running app,
not terminal commands.

| Number | Action | Follow-up input |
| --- | --- | --- |
| `1` | Show restaurants and dishes | None |
| `2` | Place an order | Customer ID, restaurant ID, dishes, delivery option |
| `3` | Assign available couriers to waiting orders | None; couriers are selected automatically |
| `4` | Record an order being picked up | Order number, for example `1` |
| `5` | Record an order being delivered | Order number |
| `6` | Cancel an order before pickup | Order number |
| `7` | Show orders, their states, totals and assigned couriers | None |
| `8` | Show couriers, availability and delivery counts | None |
| `9` | Check order/courier consistency | None |
| `0` | Quit | None |

## Customers, restaurants and couriers

The program loads these records at startup. IDs and dish names are case-sensitive.

| Customer ID | Name |
| --- | --- |
| `C1` | Ana |
| `C2` | Petar |
| `C3` | Maja |
| `C4` | Luka |

| Restaurant ID | Name | Available dishes and prices |
| --- | --- | --- |
| `R1` | Pizza Place | Pizza: 8.50; Cola: 2.00; Salad: 6.00 |
| `R2` | Sushi Bar | Sushi Roll: 12.00; Miso Soup: 4.00 |

| Courier ID | Name | Transport |
| --- | --- | --- |
| `K1` | Marko | Bike |
| `K2` | Jelena | Car |
| `K3` | Ivan | Walking |

The menu does not provide customer, restaurant or courier registration. These
sample records are defined in `delivery/producer/sample_data.py`.

## Walkthrough: place and deliver an order

Start a fresh session with `python3 main.py --menu`, then follow these steps:

| Step | Prompt or action | Enter |
| --- | --- | --- |
| 1 | Choose an action | `2` |
| 2 | Customer ID | `C1` |
| 3 | Restaurant ID | `R1` |
| 4 | Items | `Pizza*2, Cola` |
| 5 | Delivery option | `standard` |
| 6 | Choose an action: dispatch waiting orders | `3` |
| 7 | Choose an action: inspect orders | `7` |
| 8 | Choose an action: record pickup | `4` |
| 9 | Order number | `1` |
| 10 | Choose an action: record delivery | `5` |
| 11 | Order number | `1` |
| 12 | Choose an action: inspect couriers | `8` |
| 13 | Choose an action: quit | `0` |

This creates order #1 for Ana with a total of **23.00**. In a fresh session using
nearest assignment, **Marko (K1)** receives it. After delivery, he becomes available
again and his delivery count increases to 1.

Item input uses commas to separate dishes and `*` for quantity:

```text
Pizza*2, Cola
Sushi Roll, Miso Soup*2
```

An omitted quantity means one. Choose dishes from the selected restaurant only.
At an order-number prompt, enter `1`, not `#1` or a courier ID.

## Choosing couriers and progressing orders

You decide when to dispatch, record pickup and record delivery. The program
selects the courier according to the policy chosen at startup:

- **Nearest:** compares courier distance to the restaurant.
- **Fastest:** compares estimated arrival time, accounting for courier speed and
  travel from courier to restaurant to customer, plus cooking time.

There is **no manual courier-selection option**. You cannot enter “K2 for order
#1.” Use `7` or `8` to see who was assigned. Pickup and delivery operate on an
order's already assigned courier.

Each courier carries one order at a time. Waiting orders are considered oldest
first. If all couriers are busy, additional orders remain `NEW`. Once a courier
is free, select `3` again to dispatch waiting orders.

```text
NEW → ASSIGNED → PICKED_UP → DELIVERED
NEW → CANCELLED
ASSIGNED → CANCELLED
```

You must dispatch before pickup and record pickup before delivery. To cancel,
select `6` and enter the order number while it is `NEW` or `ASSIGNED`.
Cancellation is unavailable after pickup. Delivery and cancellation do not
trigger automatic dispatch of another order.

## Delivery options

| Option | Delivery fee | Cooking time used in estimates |
| --- | --- | --- |
| `standard` | 2.00 + 0.50 per km | 20 minutes |
| `express` | 5.00 + 1.00 per km | 10 minutes |

Press Enter at the delivery-option prompt to use `standard`. The order total is
food cost plus delivery fee. Distance is measured along a grid. Express changes
pricing and estimated cooking time; it does not move an order ahead in the queue.

## Logs and session data

Logs append to `logs/app.log` inside the project folder. Use `--log-file` to select
a different file, and `--log-console` to also show logs in the terminal. Supported
standard levels include `DEBUG`, `INFO`, `WARNING` and `ERROR`; the default is INFO.
Unexpected exceptions after logging is configured are recorded with their traceback
in the log file, then re-raised so the program still reports the failure in the
terminal.

Customers, restaurants, couriers and orders are saved in `data/delivery.db` and
restored on the next `--menu` or `--web` start. Delete that file to start over.
Notifications are displayed messages; no SMS or email is sent. Pickup and delivery
are recorded immediately when selected, with no background driving simulation.

Option `9` checks selected order/courier consistency rules. It reports problems
but does not repair them or guarantee that every possible error has been detected.

## Project structure

```text
delivery/
  common/         Domain objects, states, builders, errors, configuration and logging
  core/           Application construction, startup and order/catalog operations
  dispatch/       Courier selection policies
  storage/        SQLite repositories, schema, loading and transactions
  observers/      Customer/restaurant messages and event logging
  reliability/    Order/courier consistency checks
  producer/       Sample city data
  console/        Interactive menu and scripted demo
  web/            Web page and its small HTTP server (local use only)
  __main__.py     Package launcher
main.py           Program launcher
docs/             Architecture guide
```

See [architecture](docs/architecture.md) for component responsibilities.

*Note - all of the .md files were Ai generated as well as 70% of the comments.
Full list of the used prompts will be included in the next commit.
Tests have not been yet created. 
