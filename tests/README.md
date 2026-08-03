# Testing tidbcloudlake-dbt

## Overview

Here are the steps to run the tests:
1. Set up
2. Get config
3. Run tests

## Set up

Make sure you have python environment, you can find the supported python version in setup.py.
```bash
pip3 install -r requirements_dev.txt
pip3 install .
```

## Get config
Config the configurations in `conftest.py`:

```python
{
        "type": "tidbcloudlake",
        "host": "host",
        "port": 443,
        "user": "user",
        "pass": "pass",
        "schema": "your database",
        "secure": True,
    }
```

You can find the connection information for your TiDB Cloud Lake warehouse in the TiDB Cloud console.

## Run tests

```shell
python -m pytest -s -vv   tests/functional
```
