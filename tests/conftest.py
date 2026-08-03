import os

import pytest

# Import the fuctional fixtures as a plugin
# Note: fixtures with session scope need to be local

pytest_plugins = ["dbt.tests.fixtures.project"]


def _env_bool(name, default):
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in ("1", "true", "yes", "on")


# The profile dictionary, used to write out profiles.yml.
# Defaults target a server on localhost; override with LAKE_TEST_* to run the
# suite against a remote TiDB Cloud Lake warehouse.
@pytest.fixture(scope="class")
def dbt_profile_target():
    target = {
        "type": "tidbcloudlake",
        "host": os.getenv("LAKE_TEST_HOST", "localhost"),
        "port": int(os.getenv("LAKE_TEST_PORT", "8000")),
        "user": os.getenv("LAKE_TEST_USER", "lake"),
        "pass": os.getenv("LAKE_TEST_PASSWORD", "lake"),
        "schema": os.getenv("LAKE_TEST_SCHEMA", "default"),
        "secure": _env_bool("LAKE_TEST_SECURE", False),
    }
    warehouse = os.getenv("LAKE_TEST_WAREHOUSE")
    if warehouse:
        target["warehouse"] = warehouse
    return target
