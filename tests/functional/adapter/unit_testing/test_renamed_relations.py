from dbt.adapters.tidbcloudlake.relation import TiDBCloudLakeRelation
from dbt.adapters.contracts.relation import RelationType


def test_renameable_relation():
    relation = TiDBCloudLakeRelation.create(
        database=None,
        schema="my_schema",
        identifier="my_table",
        type=RelationType.Table,
    )
    assert relation.renameable_relations == frozenset(
    )
