"""Validate metadata types as type expressions before placing them in SQL."""

import re

from dbt_common.exceptions import CompilationError

from dbt.adapters.tidbcloudlake.identifiers import quote_identifier

_TOKEN = re.compile(
    r'\s*("(?:""|[^"])*"|`(?:``|[^`])*`|[^\W\d][\w$]*|[0-9]+|[(),])', re.UNICODE
)
_SCALARS = set("""
NULL BOOL BOOLEAN TINYINT SMALLINT INT INTEGER BIGINT UTINYINT USMALLINT UINT UBIGINT
INT8 INT16 INT32 INT64 INT128 UINT8 UINT16 UINT32 UINT64 UINT128
FLOAT DOUBLE FLOAT32 FLOAT64 REAL STRING VARCHAR CHAR TEXT CHARACTER BINARY VARBINARY
DATE DATE32 DATETIME DATETIME64 TIMESTAMP TIMESTAMP_TZ TIMESTAMPTZ TIME INTERVAL DECIMAL NUMERIC NUMBER
VARIANT JSON BITMAP GEOMETRY GEOGRAPHY EMPTYARRAY EMPTYMAP
""".split())
_SIZED = set(
    "VARCHAR CHAR CHARACTER BINARY VARBINARY FLOAT DATETIME DATETIME64 TIMESTAMP TIME DECIMAL NUMERIC NUMBER GEOMETRY GEOGRAPHY".split()
)
_INTEGER = set("TINYINT SMALLINT INT INTEGER BIGINT INT8 INT16 INT32 INT64".split())


class _TypeParser:
    def __init__(self, text):
        if not isinstance(text, str) or not text or len(text) > 65536:
            self.fail()
        self.tokens = []
        offset = 0
        while offset < len(text):
            if not text[offset:].strip():
                break
            match = _TOKEN.match(text, offset)
            if match is None:
                self.fail()
            self.tokens.append(match.group(1))
            offset = match.end()
        self.index = 0

    @staticmethod
    def fail():
        raise CompilationError("Invalid or unsupported Lake metadata type expression")

    def peek(self, delta=0):
        index = self.index + delta
        return self.tokens[index] if index < len(self.tokens) else None

    def take(self, expected=None):
        token = self.peek()
        if token is None or (expected is not None and token.upper() != expected):
            self.fail()
        self.index += 1
        return token

    def type(self, depth=0):
        if depth >= 64:
            self.fail()
        name = self.take()
        upper = name.upper()
        if upper in ("NULLABLE", "ARRAY", "MAP", "TUPLE", "VECTOR"):
            self.take("(")
            if upper == "VECTOR" and self.peek() and self.peek().isdigit():
                dimension = self.number()
                self.take(")")
                return self.nullability(name + "(" + dimension + ")")
            parts = []
            while True:
                if upper == "TUPLE" and self._named_field():
                    field = self.take()
                    if field[0] in ('"', "`"):
                        field = field[1:-1].replace(field[0] * 2, field[0])
                    parts.append(quote_identifier(field) + " " + self.type(depth + 1))
                elif upper == "VECTOR" and parts:
                    parts.append(self.number())
                else:
                    parts.append(self.type(depth + 1))
                if self.peek() != ",":
                    break
                self.take(",")
            self.take(")")
            arity = {"NULLABLE": 1, "ARRAY": 1, "MAP": 2, "VECTOR": 2}
            if upper in arity and len(parts) != arity[upper]:
                self.fail()
            return self.nullability(name + "(" + ", ".join(parts) + ")")
        if upper not in _SCALARS:
            self.fail()
        if upper == "DOUBLE" and self.peek() and self.peek().upper() == "PRECISION":
            name += " " + self.take("PRECISION")
        elif upper == "CHARACTER" and self.peek() and self.peek().upper() == "VARYING":
            name += " " + self.take("VARYING")
        elif upper == "TIMESTAMP" and self.peek() and self.peek().upper() == "WITH":
            name += (
                " "
                + self.take("WITH")
                + " "
                + self.take("TIME")
                + " "
                + self.take("ZONE")
            )
        if self.peek() == "(":
            if upper not in _SIZED:
                self.fail()
            self.take("(")
            prefix = ""
            if (
                upper in ("GEOMETRY", "GEOGRAPHY")
                and self.peek()
                and self.peek().upper() == "SRID"
            ):
                prefix = self.take("SRID") + " "
            numbers = [self.number()]
            if self.peek() == ",":
                self.take(",")
                numbers.append(self.number())
            self.take(")")
            if len(numbers) > 1 and upper not in ("DECIMAL", "NUMERIC", "NUMBER"):
                self.fail()
            name += "(" + prefix + ", ".join(numbers) + ")"
        if self.peek() and self.peek().upper() == "UNSIGNED":
            if upper not in _INTEGER:
                self.fail()
            name += " " + self.take("UNSIGNED")
        return self.nullability(name)

    def nullability(self, name):
        if self.peek() and self.peek().upper() == "NOT":
            return name + " " + self.take("NOT") + " " + self.take("NULL")
        if self.peek() and self.peek().upper() == "NULL":
            return name + " " + self.take("NULL")
        return name

    def number(self):
        token = self.take()
        if not token.isascii() or not token.isdigit():
            self.fail()
        return token

    def _named_field(self):
        first, second = self.peek(), self.peek(1)
        if first and first[0] in ('"', "`"):
            return True
        if (
            first
            and second
            and (
                second.upper() in _SCALARS
                or second.upper() in ("NULLABLE", "ARRAY", "MAP", "TUPLE", "VECTOR")
            )
        ):
            return True
        return False


def validate_type_expression(text: str) -> str:
    parser = _TypeParser(text)
    result = parser.type()
    if parser.peek() is not None:
        parser.fail()
    return result
