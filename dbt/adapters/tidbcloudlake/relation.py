from dataclasses import dataclass, field
from typing import Optional, TypeVar, Any, Type, Dict, Union, Iterator, Tuple, Set

from dbt_common.exceptions import CompilationError, DbtDatabaseError, DbtRuntimeError, DbtInternalError
from dbt.adapters.base.relation import BaseRelation, Policy
from dbt.adapters.contracts.relation import (
    Path,
    RelationType,
)


@dataclass
class TiDBCloudLakeQuotePolicy(Policy):
    database: bool = False
    schema: bool = False
    identifier: bool = False


@dataclass
class TiDBCloudLakeIncludePolicy(Policy):
    database: bool = False
    schema: bool = True
    identifier: bool = True


Self = TypeVar("Self", bound="TiDBCloudLakeRelation")


@dataclass(frozen=True, eq=False, repr=False)
class TiDBCloudLakeRelation(BaseRelation):
    quote_policy: Policy = field(default_factory=lambda: TiDBCloudLakeQuotePolicy())
    include_policy: TiDBCloudLakeIncludePolicy = field(
        default_factory=lambda: TiDBCloudLakeIncludePolicy()
    )
    quote_character: str = ""

    def __post_init__(self):
        if self.database != self.schema and self.database:
            raise DbtDatabaseError(
                f"    schema: {self.schema} \n"
                f"    database: {self.database} \n"
                f"On TiDB Cloud Lake, database must be omitted or have the same value as"
                f" schema."
            )

    @classmethod
    def create(
            cls: Type[Self],
            database: Optional[str] = None,
            schema: Optional[str] = None,
            identifier: Optional[str] = None,
            rt: Optional[RelationType] = None,
            **kwargs,
    ) -> Self:
        database = None
        kwargs.update(
            {
                "path": {
                    "database": database,
                    "schema": schema,
                    "identifier": identifier,
                },
                "type": rt,
            }
        )
        return cls.from_dict(kwargs)

    def render(self):
        if self.include_policy.database and self.include_policy.schema:
            raise DbtRuntimeError(
                "Got a TiDB Cloud Lake relation with schema and database set to "
                "include, but only one can be set"
            )
        return super().render()

    @classmethod
    def get_path(
            cls, relation: BaseRelation, information_schema_view: Optional[str]
    ) -> Path:
        Path.database = None
        return Path(
            database=None,
            schema=relation.schema,
            identifier="INFORMATION_SCHEMA",
        )

    def matches(
            self,
            database: Optional[str] = None,
            schema: Optional[str] = None,
            identifier: Optional[str] = None,
    ):
        if database:
            raise DbtRuntimeError(
                f"Passed unexpected schema value {schema} to Relation.matches"
            )
        return self.schema == schema and self.identifier == identifier
