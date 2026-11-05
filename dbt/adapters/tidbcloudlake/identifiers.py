"""Render names as identifiers, never as SQL fragments."""

import re

from dbt_common.exceptions import CompilationError

_BARE_IDENTIFIER = re.compile(r"[^\W\d][\w$]*\Z", re.UNICODE)


def quote_identifier(identifier: str) -> str:
    if not isinstance(identifier, str) or not identifier or "\x00" in identifier:
        raise CompilationError(
            "Lake identifiers must be non-empty strings without NUL bytes"
        )
    # Some Lake lexer versions treat a backslash before a double quote as
    # an escape. Backtick-delimited names keep those backslashes literal.
    delimiter = "`" if "\\" in identifier else '"'
    return delimiter + identifier.replace(delimiter, delimiter * 2) + delimiter


def unquoted_identifier(identifier: str) -> str:
    if not isinstance(identifier, str) or not _BARE_IDENTIFIER.fullmatch(identifier):
        raise CompilationError(
            "Unsafe unquoted Lake identifier; enable identifier quoting "
            "(quote_columns: true for seed headers)"
        )
    return identifier


def protect_quoted_percents(sql: str) -> str:
    """Keep DB-API placeholders out of SQL names, literals and comments.

    Python's percent formatter does not understand SQL. A seed header named
    ``%s`` must never consume a bound value inside its identifier delimiters.
    Only percent signs in SQL code participate in parameter substitution.
    """
    chunks = []
    index = 0
    while index < len(sql):
        start = index
        char = sql[index]
        if char in ("'", '"', "`"):
            index += 1
            while index < len(sql):
                if char == "'" and sql[index] == "\\":
                    index += 2
                elif sql[index] == char:
                    index += 1
                    if index < len(sql) and sql[index] == char:
                        index += 1
                    else:
                        break
                else:
                    index += 1
            chunks.append(sql[start:index].replace("%", "%%"))
        elif sql.startswith("--", index):
            end = sql.find("\n", index)
            index = len(sql) if end < 0 else end
            chunks.append(sql[start:index].replace("%", "%%"))
        elif sql.startswith("/*", index):
            end = sql.find("*/", index + 2)
            index = len(sql) if end < 0 else end + 2
            chunks.append(sql[start:index].replace("%", "%%"))
        else:
            chunks.append(char)
            index += 1
    return "".join(chunks)
