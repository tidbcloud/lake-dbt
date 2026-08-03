from dbt.adapters.tidbcloudlake.connections import TiDBCloudLakeConnectionManager  # noqa
from dbt.adapters.tidbcloudlake.connections import TiDBCloudLakeCredentials
from dbt.adapters.tidbcloudlake.impl import TiDBCloudLakeAdapter
from dbt.adapters.tidbcloudlake.column import TiDBCloudLakeColumn  # noqa
from dbt.adapters.tidbcloudlake.relation import TiDBCloudLakeRelation  # noqa

from dbt.adapters.base import AdapterPlugin
from dbt.include import tidbcloudlake


Plugin = AdapterPlugin(
    adapter=TiDBCloudLakeAdapter,
    credentials=TiDBCloudLakeCredentials,
    include_path=tidbcloudlake.PACKAGE_PATH,
)
