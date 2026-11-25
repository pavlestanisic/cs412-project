"""Configure logging, assemble the application, and run the console."""

import os

from delivery.common.config import parse_args
from delivery.common.logging import get_logger, setup_logging
from delivery.core.factory import build_app
from delivery.producer.sample_data import load_sample_data
from delivery.storage.database import DATABASE_PATH, IN_MEMORY
from delivery.console.app import ConsoleApp
from delivery.web.server import serve

def main(argv=None, output=print, input_func=input):
    """Run the app. Returns the process exit code (0 = success)."""
    args = parse_args(argv)

    # Make sure the log folder exists before the file handler opens the file.
    os.makedirs(os.path.dirname(os.path.abspath(args.log_file)), exist_ok=True)
    setup_logging(args.log_level, args.log_file, args.log_console)
    log = get_logger("delivery.core.entrypoint")
    log.debug("App started (menu=%s, web=%s, dispatcher=%s)", args.menu, args.web, args.dispatcher)

    # The menu and the web page keep their work in data/delivery.db between
    # runs. The scripted demo refers to orders #1-#4, so it always starts
    # from an empty database.
    database = DATABASE_PATH if (args.menu or args.web) else IN_MEMORY

    app = None
    try:
        app = build_app(dispatcher_name=args.dispatcher, database=database)
        load_sample_data(app)
        console = ConsoleApp(app, output=output, input_func=input_func)

        if args.menu:
            console.run_menu()
            healthy = app.health.is_healthy()
        elif args.web:
            serve(app, port=args.port, output=output)
            healthy = app.health.is_healthy()
        else:
            healthy = console.run_demo()
    except Exception:
        log.exception("Application failed")
        raise
    finally:
        if app is not None:
            app.close()

    log.info("App finished, healthy=%s", healthy)
    return 0 if healthy else 1
