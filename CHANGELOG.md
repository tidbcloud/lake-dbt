# tidbcloudlake-dbt Changelog

- This file provides a full account of all changes to `tidbcloudlake-dbt`.
- Changes are listed under the (pre)release in which they first appear. Subsequent releases include changes from previous releases.
- "Breaking changes" listed under a version may require action from end users or external maintainers when upgrading to that version.

## 1.8.1

- Initial release of the TiDB Cloud Lake adapter for dbt.
- Connections are made through the [tidbcloudlake-driver](https://github.com/tidbcloud/lakesql/tree/main/bindings/python)
  Python binding using a `lake://` DSN.
- Added an optional `warehouse` profile option.
- `dbt docs generate` now produces a full catalog: column names, ordinals and
  types, plus table type, comment and owner.
