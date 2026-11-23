import sqlite3
from contextlib import contextmanager
from pathlib import Path


PROJECT_FOLDER = Path(__file__).resolve().parents[2]
DATABASE_PATH = PROJECT_FOLDER / "data" / "delivery.db"
SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


@contextmanager
def get_connection():
    """Open a connection and close it when the operation finishes."""
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row

    try:
        connection.execute("PRAGMA foreign_keys = ON")

        yield connection

        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize_database():
    """Create the tables and indexes defined in schema.sql."""
    schema = SCHEMA_PATH.read_text(encoding="utf-8")

    with get_connection() as connection:
        # Execute the schema together so a failure rolls back its changes.
        connection.executescript("BEGIN;\n" + schema)

    print(f"Database initialized: {DATABASE_PATH}")


if __name__ == "__main__":
    initialize_database()