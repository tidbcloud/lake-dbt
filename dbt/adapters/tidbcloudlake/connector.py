"""A thin PEP 249 wrapper around ``tidbcloudlake-driver``.

The driver already exposes a cursor with the DB-API surface, but it has no
connection object that dbt can open, commit, roll back and close.  This module
adds that missing layer so ``dbt.adapters.tidbcloudlake.connections`` can treat
it like any other DB-API driver.

Parameters are interpolated client side rather than handed to the driver: dbt
binds ``date``, ``datetime``, ``Decimal`` and ``None`` values (seeds especially),
which the driver's native placeholders do not accept.

See https://github.com/tidbcloud/lakesql/tree/main/bindings/python
"""

import decimal
import json
import re
from datetime import date, datetime, time, timedelta
from typing import Any, Optional, Sequence

from tidbcloudlake_driver import BlockingLakeClient
from tidbcloudlake_driver import Error, NotSupportedError  # noqa: F401

# PEP 249 module globals
apilevel = "2.0"
threadsafety = 2  # Threads may share the module and connections.
paramstyle = "pyformat"  # Python extended format codes, e.g. ...WHERE name=%(name)s
Binary = bytes


class ParamEscaper:
    def escape_args(self, parameters):
        if isinstance(parameters, dict):
            return {k: self.escape_item(v) for k, v in parameters.items()}
        elif isinstance(parameters, (list, tuple)):
            return tuple(self.escape_item(x) for x in parameters)
        else:
            raise Error("Unsupported param format: {}".format(parameters))

    def escape_number(self, item):
        return item

    def escape_string(self, item):
        if isinstance(item, bytes):
            item = item.decode("utf-8")
        return "'{}'".format(
            item.replace("\\", "\\\\").replace("'", "\\'").replace("%", "%%")
        )

    def escape_item(self, item):
        if item is None:
            return "NULL"
        elif isinstance(item, bool):
            return "TRUE" if item else "FALSE"
        elif isinstance(item, (int, float)):
            return self.escape_number(item)
        elif isinstance(item, decimal.Decimal):
            return self.escape_number(item)
        elif isinstance(item, timedelta):
            return self.escape_string(f"{item.total_seconds()} seconds") + "::interval"
        elif isinstance(item, time):
            # N.B. the date here is arbitrary but must be stable
            return (
                self.escape_string(item.strftime("1970-01-01 %H:%M:%S.%f"))
                + "::timestamp"
            )
        elif isinstance(item, datetime):
            return (
                self.escape_string(item.strftime("%Y-%m-%d %H:%M:%S.%f")) + "::timestamp"
            )
        elif isinstance(item, date):
            return self.escape_string(item.strftime("%Y-%m-%d")) + "::date"
        elif isinstance(item, dict):
            return self.escape_string(f"parse_json({json.dumps(item)})")
        else:
            return self.escape_string(item)


_escaper = ParamEscaper()

RE_INSERT_VALUES = re.compile(
    r"\s*((?:INSERT|REPLACE)\s.+\sVALUES?\s*)"
    + r"(\(\s*(?:%s|%\(.+\)s)\s*(?:,\s*(?:%s|%\(.+\)s)\s*)*\))"
    + r"(\s*(?:ON DUPLICATE.*)?);?\s*\Z",
    re.IGNORECASE | re.DOTALL,
)


def connect(dsn: str) -> "Connection":
    """Open a connection to TiDB Cloud Lake.

    ``dsn`` is a lakesql DSN, e.g.
    ``lake://user:password@host:port/database?sslmode=disable``.
    """
    return Connection(dsn)


class Connection:
    """A stateless factory for cursors, which do all the real work."""

    def __init__(self, dsn: str = "lake://root:@localhost:8000/?sslmode=disable"):
        self.client = BlockingLakeClient(dsn)
        self._cursors: list = []

    def cursor(self) -> "Cursor":
        cursor = Cursor(self.client.cursor())
        self._cursors.append(cursor)
        return cursor

    def close(self) -> None:
        for cursor in self._cursors:
            try:
                cursor.close()
            except Exception:  # pragma: no cover - best effort cleanup
                pass
        self._cursors = []

    def commit(self) -> None:
        """TiDB Cloud Lake statements are auto-committed."""

    def rollback(self) -> None:
        raise NotSupportedError("Transactions are not supported")


class Cursor:
    """Manages the context of a single fetch operation.

    Cursors are not isolated: changes made through one cursor are immediately
    visible to other cursors and connections.
    """

    def __init__(self, inner):
        self.inner = inner

    @property
    def description(self):
        """A sequence of 7-item sequences, one per result column.

        Each entry is ``(name, type_code, display_size, internal_size,
        precision, scale, null_ok)``; everything after ``type_code`` may be
        ``None``.
        """
        try:
            return self.inner.description
        except Exception as e:
            raise Error(str(e)) from e

    @property
    def rowcount(self) -> int:
        try:
            return self.inner.rowcount
        except Exception as e:
            raise Error(str(e)) from e

    def close(self) -> None:
        try:
            self.inner.close()
        except Exception as e:
            raise Error(str(e)) from e

    def mogrify(self, query: str, parameters: Optional[Sequence[Any]]) -> str:
        if parameters:
            query = query % _escaper.escape_args(parameters)
        return query

    def execute(self, operation: str, parameters: Optional[Sequence[Any]] = None):
        """Prepare and execute a database operation (query or command)."""
        # Blank statements are skipped: dbt emits them for materializations
        # whose hooks compile down to nothing.
        if not operation or not operation.strip():
            return None

        try:
            query = self.mogrify(operation, parameters)
            if parameters:
                query = query.replace("%%", "%")
            return self.inner.execute(query)
        except Exception as e:
            raise Error(str(e)) from e

    def executemany(self, operation: str, seq_of_parameters: Sequence[Sequence[Any]]):
        """Execute ``operation`` once per entry in ``seq_of_parameters``.

        Multi-row ``INSERT``s are collapsed into a single statement; anything
        else falls back to one round trip per parameter set. Only the final
        result set is retained.
        """
        match = RE_INSERT_VALUES.match(operation)
        if not match:
            for parameters in seq_of_parameters:
                self.execute(operation, parameters)
            return None

        try:
            q_prefix = match.group(1)
            q_values = match.group(2).rstrip()

            values_list = [
                q_values % _escaper.escape_args(parameters)
                for parameters in seq_of_parameters
            ]
            query = "{} {};".format(q_prefix, ",".join(values_list))
            return self.inner.execute(query)
        except Exception as e:
            raise Error(str(e)) from e

    def fetchone(self):
        """Return the next row, or ``None`` when no more data is available."""
        try:
            row = self.inner.fetchone()
            if row is None:
                return None
            return row.values()
        except Exception as e:
            raise Error(str(e)) from e

    def fetchmany(self, size: int = 1):
        """Return up to ``size`` rows; an empty sequence when exhausted."""
        try:
            rows = self.inner.fetchmany(size)
            return [row.values() for row in rows]
        except Exception as e:
            raise Error(str(e)) from e

    def fetchall(self):
        """Return all remaining rows as a sequence of sequences."""
        try:
            rows = self.inner.fetchall()
            return [row.values() for row in rows]
        except Exception as e:
            raise Error(str(e)) from e

    def __next__(self):
        """Same semantics as :py:meth:`fetchone`, raising ``StopIteration``
        once the result set is exhausted."""
        try:
            return self.inner.__next__().values()
        except StopIteration:
            raise
        except Exception as e:
            raise Error(str(e)) from e

    next = __next__

    def __iter__(self):
        return self
