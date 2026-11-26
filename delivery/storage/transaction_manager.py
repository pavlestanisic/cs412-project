"""
UNIT OF WORK - one change, saved completely or not at all.

Services wrap each change in `with transactions.transaction() as connection:`
and pass that connection to the repositories. The repositories never commit.
"""

from contextlib import contextmanager


class TransactionManager:
    """Run a group of database changes as one all-or-nothing transaction."""

    def __init__(self, connection):
        self._connection = connection

    @contextmanager
    def transaction(self):
        """
        Commit when the block finishes, roll back when it raises.

        Only the database is rolled back. Python objects changed inside the
        block keep their changes, so the caller must throw them away itself.
        """
        if self._connection.in_transaction:
            raise RuntimeError("A transaction is already running.")

        # IMMEDIATE takes the write lock now, so another app writing to the
        # same file cannot slip in between our reads and our writes.
        self._connection.execute("BEGIN IMMEDIATE")
        try:
            yield self._connection
            self._connection.commit()
        except BaseException:
            self._connection.rollback()
            raise
