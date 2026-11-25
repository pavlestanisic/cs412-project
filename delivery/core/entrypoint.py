"""Configure logging, assemble the application, and run the console."""

import os

from delivery.common.config import parse_args
from delivery.common.logging import get_logger, setup_logging
from delivery.core.factory import build_app
from delivery.producer.sample_data import load_sample_data
from delivery.storage.database import initialize_database 
from delivery.storage.customer_repository import CustomerRepository
from delivery.storage.restaurant_repository import RestaurantRepository
from delivery.console.app import ConsoleApp

def main(argv=None, output=print, input_func=input):
    """Run the app. Returns the process exit code (0 = success)."""
    args = parse_args(argv)

    # Make sure the log folder exists before the file handler opens the file.
    os.makedirs(os.path.dirname(os.path.abspath(args.log_file)), exist_ok=True)
    setup_logging(args.log_level, args.log_file, args.log_console)
    log = get_logger("delivery.core.entrypoint")
    log.debug("App started (menu=%s, dispatcher=%s)", args.menu, args.dispatcher)

    try:
        initialize_database()

        app = build_app(dispatcher_name=args.dispatcher,
                        customer_repository=CustomerRepository(),
                        restaurant_repository=RestaurantRepository())
        load_sample_data(app)
        console = ConsoleApp(app, output=output, input_func=input_func)

        if args.menu:
            console.run_menu()
            healthy = app.health.is_healthy()
        else:
            healthy = console.run_demo()
    except Exception:
        log.exception("Application failed")
        raise

    log.info("App finished, healthy=%s", healthy)
    return 0 if healthy else 1
