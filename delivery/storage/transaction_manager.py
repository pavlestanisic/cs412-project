from contextlib import contextmanager
from delivery.storage.database import get_connection

class TransactionManager:
    """Manage database transactions using a context manager."""

    @contextmanager
    def transaction(self):
        """Start a transaction and commit or rollback on exit."""
        with get_connection() as connection:
            connection.execute("BEGIN IMMEDIATE;")
            yield connection
            