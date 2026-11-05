"""Exercise rendered SQL against Lake, including the actual dbt seed bind path."""

import csv
import io

import pytest
from dbt.tests.util import run_dbt

from dbt.adapters.tidbcloudlake.column import TiDBCloudLakeColumn
from dbt.adapters.tidbcloudlake.identifiers import quote_identifier
from dbt.adapters.tidbcloudlake.relation import TiDBCloudLakeRelation
from dbt.adapters.contracts.relation import RelationType

HEADERS = [
    "MixedCase",
    "select",
    'a"b',
    "a`b",
    'a\\"b',
    "%s",
    "a%%b",
    "comma, name",
    "id) VALUES (1); DROP TABLE sentinel; --",
]


def relation(project, name):
    return TiDBCloudLakeRelation.create(
        schema=project.test_schema, identifier=name, rt=RelationType.Table
    )


class TestIdentifierSecurity:
    @pytest.fixture(scope="class")
    def seeds(self):
        stream = io.StringIO(newline="")
        writer = csv.writer(stream)
        writer.writerow(HEADERS)
        writer.writerow(list(range(1, len(HEADERS) + 1)))
        return {"quoted_seed.csv": stream.getvalue()}

    @pytest.fixture(scope="class")
    def models(self):
        return {
            "quoted_model.sql": "{{ config(materialized='table') }} select * from {{ ref('quoted_seed') }}"
        }

    @pytest.fixture(scope="class")
    def project_config_update(self):
        return {"seeds": {"+quote_columns": True}}

    def test_seed_model_metadata_and_destructive_macros(self, project):
        sentinel = relation(project, "sentinel")
        project.run_sql(f"CREATE TABLE {sentinel} (id INT)")
        project.run_sql(f"INSERT INTO {sentinel} VALUES (999)")
        run_dbt(["seed"])
        run_dbt(["run"])
        seed, model = relation(project, "quoted_seed"), relation(
            project, "quoted_model"
        )
        columns = ", ".join(quote_identifier(name) for name in HEADERS)
        expected = tuple(range(1, len(HEADERS) + 1))
        assert (
            tuple(project.run_sql(f"SELECT {columns} FROM {seed}", fetch="one"))
            == expected
        )
        assert (
            tuple(project.run_sql(f"SELECT {columns} FROM {model}", fetch="one"))
            == expected
        )
        with project.adapter.connection_named("identifier_metadata"):
            found = project.adapter.get_columns_in_relation(seed)
        assert [column.name for column in found] == HEADERS
        comparison = project.adapter.get_rows_different_sql(seed, model, HEADERS)
        assert tuple(project.run_sql(comparison, fetch="one")) == (0, 0)

        for name in ['x"; DROP TABLE sentinel; --', "space name", "資料", 'a\\`"b']:
            source = relation(project, name)
            target = relation(project, name + "_renamed")
            column = quote_identifier('c\\"%s')
            project.run_sql(f"CREATE TABLE {source} ({column} INT)")
            project.run_sql(f"INSERT INTO {source} VALUES (7)")
            with project.adapter.connection_named("identifier_metadata"):
                found = project.adapter.list_relations_without_caching(
                    relation(project, None)
                )
                listed = next(r for r in found if r.identifier == name)
                assert listed.render() == source.render()
                assert (
                    project.adapter.get_columns_in_relation(listed)[0].name == 'c\\"%s'
                )
                project.adapter.rename_relation(listed, target)
                project.adapter.truncate_relation(target)
                project.adapter.drop_relation(target)
            assert project.run_sql(f"SELECT id FROM {sentinel}", fetch="one")[0] == 999

    def test_nested_metadata_types_round_trip(self, project):
        target = relation(project, "nested_types")
        types = [
            "Int64",
            "Nullable(String)",
            "Decimal(38, 8)",
            "Array(Nullable(Int32))",
            "Map(String, Variant)",
            'Tuple("a""b" Int32, "space name" String)',
        ]
        ddl = ", ".join(
            TiDBCloudLakeColumn("c" + str(i), dtype).quoted + " " + dtype
            for i, dtype in enumerate(types)
        )
        project.run_sql(f"CREATE TABLE {target} ({ddl})")
        with project.adapter.connection_named("type_metadata"):
            columns = project.adapter.get_columns_in_relation(target)
        assert len(columns) == len(types)
        # Parse metadata types back into real expressions, rather than comparing
        # strings from an independent implementation of the quoting rules.
        for column in columns:
            project.run_sql(
                f"SELECT CAST(NULL AS Nullable({column.data_type}))", fetch="one"
            )

    def test_percent_names_and_values_round_trip(self, project):
        target = relation(project, "percent_values")
        column = quote_identifier('value\\`"%s')
        project.run_sql(f"CREATE TABLE {target} ({column} String)")
        values = ["50%", "50%%", "O'Reilly \\", "'); DROP TABLE percent_values; --"]
        with project.adapter.connection_named("percent_values"):
            connection = project.adapter.connections.get_thread_connection()
            cursor = connection.handle.cursor()
            statement = f"INSERT INTO {target} ({column}) VALUES (%s)"
            cursor.execute(statement, [values[0]])
            cursor.executemany(statement, [(value,) for value in values[1:]])
            cursor.execute(f"SELECT {column} FROM {target}")
            assert sorted(row[0] for row in cursor.fetchall()) == sorted(values)
            cursor.close()
