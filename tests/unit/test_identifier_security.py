from types import SimpleNamespace
from unittest.mock import Mock

import agate
import pytest
from dbt_common.exceptions import CompilationError

from dbt.adapters.tidbcloudlake.column import TiDBCloudLakeColumn
from dbt.adapters.tidbcloudlake.data_types import validate_type_expression
from dbt.adapters.tidbcloudlake.identifiers import quote_identifier
from dbt.adapters.tidbcloudlake.impl import TiDBCloudLakeAdapter
from dbt.adapters.tidbcloudlake.relation import TiDBCloudLakeRelation

NAMES = [
    "normal",
    "select",
    "MixedCase",
    "space name",
    "資料",
    "a.b",
    "a`b",
    'a"b',
    'a\\"b',
    'x"; DROP TABLE sentinel; --',
    "{name}",
    "line\nbreak",
]


@pytest.fixture
def adapter():
    return TiDBCloudLakeAdapter.__new__(TiDBCloudLakeAdapter)


def test_absent_catalog_stays_absent(adapter):
    assert adapter.quote(None) is None


def test_configured_unquoted_names_cannot_bypass_validation(adapter):
    adapter.config = SimpleNamespace(quoting={"identifier": False})
    assert adapter.quote_as_configured("MixedCase", "identifier") == "MixedCase"
    with pytest.raises(CompilationError):
        adapter.quote_as_configured('x"; SELECT 1; --', "identifier")
    with pytest.raises(CompilationError):
        adapter.quote_as_configured('x"; SELECT 1; --', "unknown")


@pytest.mark.parametrize("name", NAMES)
def test_all_name_renderers_use_the_same_single_identifier(adapter, name):
    delimiter = "`" if "\\" in name else '"'
    expected = delimiter + name.replace(delimiter, delimiter * 2) + delimiter
    assert adapter.quote(name) == expected
    assert TiDBCloudLakeColumn(name, "Int64").quoted == expected
    relation = TiDBCloudLakeRelation.create(schema=name, identifier=name)
    assert relation.render() == expected + "." + expected
    assert relation.quoted(name) == expected


@pytest.mark.parametrize("name", ["", None, 123, "bad\x00name"])
def test_invalid_names_rejected(name):
    with pytest.raises(CompilationError):
        quote_identifier(name)


def test_explicit_unquoted_policy_keeps_legacy_case_folding_for_simple_names():
    relation = TiDBCloudLakeRelation.create(
        schema="MySchema",
        identifier="MyTable",
        quote_policy={"schema": False, "identifier": False},
    )
    assert relation.render() == "MySchema.MyTable"
    unicode_relation = TiDBCloudLakeRelation.create(
        schema="資料",
        identifier="a$b",
        quote_policy={"schema": False, "identifier": False},
    )
    assert unicode_relation.render() == "資料.a$b"


@pytest.mark.parametrize("name", [name for name in NAMES[3:] if name != "資料"])
def test_false_quoting_policy_cannot_emit_an_sql_fragment(name):
    relation = TiDBCloudLakeRelation.create(
        schema="default", identifier=name, quote_policy={"identifier": False}
    )
    with pytest.raises(CompilationError):
        relation.render()


@pytest.mark.parametrize("flag", [None, True, False])
def test_seed_headers_are_not_a_bypass(adapter, flag):
    name = "id) VALUES (1); DROP TABLE sentinel; --"
    if flag is False:
        with pytest.raises(CompilationError):
            adapter.quote_seed_column(name, flag)
        assert adapter.quote_seed_column("MixedCase", flag) == "MixedCase"
    else:
        assert adapter.quote_seed_column(name, flag) == quote_identifier(name)


def test_server_metadata_and_test_comparison_use_safe_names(adapter):
    name = 'x"; DROP TABLE sentinel; --'
    adapter.execute_macro = Mock(return_value=[(None, name, "default", "table")])
    relations = adapter.list_relations_without_caching(
        SimpleNamespace(schema="default")
    )
    assert str(relations[0]) == '"default".' + quote_identifier(name)
    sql = adapter.get_rows_different_sql(relations[0], relations[0], [name])
    assert "A." + quote_identifier(name) in sql
    assert "B." + quote_identifier(name) in sql
    assert str(relations[0]) in sql


@pytest.mark.parametrize(
    "dtype",
    [
        "Int64",
        "Nullable(String)",
        "Decimal(38, 8)",
        "Timestamp(6)",
        "Int UNSIGNED",
        "Array(Nullable(Int32))",
        "Map(String, Array(Tuple(Int8, Variant)))",
        'Tuple(a String, "b""c" Array(Nullable(Int64)))',
        "Vector(Float32, 3)",
        "Double Precision",
        "Character Varying(128)",
        "Geometry(SRID 4326)",
        "Vector(3)",
        "Interval",
        "Timestamp_TZ",
        "Timestamp With Time Zone",
        "Int64 NOT NULL",
        "Array(Int64 NULL)",
        "Tuple(a$b String)",
    ],
)
def test_nested_metadata_types_remain_type_expressions(dtype):
    column = TiDBCloudLakeColumn("c", dtype)
    assert (
        column.literal("NULL")
        == "CAST(NULL AS " + validate_type_expression(dtype) + ")"
    )
    assert ";" not in column.data_type


@pytest.mark.parametrize(
    "dtype",
    [
        "Int); DROP TABLE sentinel; --",
        "Int) UNION SELECT (1",
        "Int DEFAULT 0",
        "Int, injected String",
        "String /* comment */",
        "String -- comment",
        "Nullable(Int64) ; SELECT 1",
        "Array(Int64",
        "Map(String)",
        "Nullable(Int, Int)",
        "Geometry(",
        "Int64\x00",
        'Tuple("x" String); SELECT 1',
        "unknown_type",
    ],
)
def test_metadata_types_cannot_append_sql(adapter, dtype):
    with pytest.raises(CompilationError):
        TiDBCloudLakeColumn("c", dtype)
    raw = agate.Table([("c", dtype)], ["name", "type"])
    with pytest.raises(CompilationError):
        adapter.parse_show_columns(None, list(raw.rows))


def test_mutated_type_is_revalidated_at_sql_render_time():
    column = TiDBCloudLakeColumn("c", "Int64")
    column.dtype = "Int); DROP TABLE sentinel; --"
    with pytest.raises(CompilationError):
        column.literal("NULL")


@pytest.mark.parametrize(
    "name", ["%s", "%(name)s", "a%b", "a%%b", "a\\`%s", 'x"; DROP TABLE sentinel; --']
)
def test_identifier_percent_signs_cannot_consume_bind_values(name):
    from dbt.adapters.tidbcloudlake.connector import Cursor

    inner = Mock()
    cursor = Cursor(inner)
    statement = (
        "INSERT INTO "
        + quote_identifier(name)
        + " ("
        + quote_identifier(name)
        + ") VALUES (%s)"
    )
    cursor.execute(statement, ["50% O'Reilly"])
    rendered = inner.execute.call_args.args[0]
    assert rendered.startswith(
        "INSERT INTO " + quote_identifier(name) + " (" + quote_identifier(name) + ")"
    )
    assert "50%" in rendered
    assert "50%%" not in rendered


def test_sql_literals_and_comments_are_not_bind_slots():
    from dbt.adapters.tidbcloudlake.connector import Cursor

    inner = Mock()
    cursor = Cursor(inner)
    cursor.execute("SELECT '%s', '50%%', %s /* %s */ -- %s\n", [1])
    inner.execute.assert_called_once_with("SELECT '%s', '50%%', 1 /* %s */ -- %s\n")
