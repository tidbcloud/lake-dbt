# tidbcloudlake-dbt


![PyPI](https://img.shields.io/pypi/v/tidbcloudlake-dbt)
![PyPI - Python Version](https://img.shields.io/pypi/pyversions/tidbcloudlake-dbt)

The `tidbcloudlake-dbt` package contains all of the code enabling [dbt](https://getdbt.com) to work with
TiDB Cloud Lake. It talks to the server through
[tidbcloudlake-driver](https://github.com/tidbcloud/lakesql/tree/main/bindings/python).

## Table of Contents
* [Installation](#installation)
* [Supported features](#supported-features)
* [Profile Configuration](#profile-configuration)
* [Running Tests](#running-tests)
* [Contributing](#contributing)

## Installation

From PyPI:

```bash
$ pip install tidbcloudlake-dbt
```

Or from source:

```bash
$ git clone https://github.com/tidbcloud/lake-dbt.git
$ cd lake-dbt
$ pip install .
```

## Supported features

| ok |           Feature           |
|:--:|:---------------------------:|
|  ✅ |    Table materialization    |
|  ✅ |    View materialization     |
|  ✅ | Incremental materialization |
|  ❌  |  Ephemeral materialization  |
|  ✅ |            Seeds            |
|  ✅ |           Sources           |
|  ✅ |      Custom data tests      |
|  ✅ |        Docs generate        |
|  ✅ |          Snapshots          |
|  ✅ |      Connection retry       |

Note:

* `Ephemeral` materialization is not supported.
* In `dbt docs generate`, views have no owner -- the server records one when a
  table is created but not when a view is.

## Profile Configuration

TiDB Cloud Lake targets should be set up using the following configuration in your `profiles.yml` file.

**Example entry for profiles.yml:**

```yaml
Your_Profile_Name:
  target: dev
  outputs:
    dev:
      type: tidbcloudlake
      host: [host]
      port: [port]
      schema: [schema(Your database)]
      user: [username]
      pass: [password]
      warehouse: [warehouse]
      secure: [SSL]
```

| Option    | Description                                          | Required? | Example                        |
|-----------|------------------------------------------------------|-----------|--------------------------------|
| type      | The specific adapter to use                          | Required  | `tidbcloudlake`                |
| host      | The server (hostname) to connect to                  | Required  | `tnxxxx.gw.aws-us-east-2.default.tidbcloud.com` |
| port      | The port to use                                      | Required  | `443`                          |
| schema    | Specify the schema (database) to build models into   | Required  | `analytics`                    |
| user      | The username to use to connect to the server         | Required  | `dbt_admin`                    |
| pass      | The password to use for authenticating to the server | Required  | `correct-horse-battery-staple` |
| warehouse | The warehouse to run queries in                      | Optional  | `default`                      |
| secure    | Whether to connect over TLS (default as True)        | Optional  | `True`                         |

These options are assembled into a lakesql DSN of the form
`lake://user:pass@host:port/schema?sslmode=require`. See the
[DSN reference](https://github.com/tidbcloud/lakesql#dsn) for the full list of
supported arguments.

## Running Tests

See [tests/README.md](tests/README.md) for details on running the integration tests.

## Contributing

Welcome to contribute for tidbcloudlake-dbt. See [Contributing Guide](CONTRIBUTING.md) for more information.
