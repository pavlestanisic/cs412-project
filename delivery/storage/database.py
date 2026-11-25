import logging
import sqlite3
from pathlib import Path


PROJECT_FOLDER = Path(__file__).resolve().parents[2]
DATABASE_PATH = PROJECT_FOLDER / "data" / "delivery.db"
SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"

# A database that lives in RAM and disappears when its connection closes.
IN_MEMORY = ":memory:"

log = logging.getLogger(__name__)


def connect(path=DATABASE_PATH):
    """
    Open the one connection the application uses for its whole run.

    isolation_level=None turns off Python's hidden automatic transactions,
    so a transaction starts only where TransactionManager says BEGIN.
    """
    if str(path) != IN_MEMORY:
        Path(path).parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(path, isolation_level=None)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database(connection):
    """Create the tables and indexes defined in schema.sql (safe to repeat)."""
    schema = SCHEMA_PATH.read_text(encoding="utf-8")

    try:
        # Run the whole schema as one transaction so a failure leaves nothing half-made.
        connection.executescript("BEGIN;\n" + schema + "\nCOMMIT;")
    except Exception:
        if connection.in_transaction:
            connection.rollback()
        raise

    log.info("Database ready")


if __name__ == "__main__":
    db_connection = connect()
    try:
        initialize_database(db_connection)
    finally:
        db_connection.close()
    print(f"Database initialized: {DATABASE_PATH}")
