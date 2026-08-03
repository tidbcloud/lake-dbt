{#
  Builds the catalog behind `dbt docs generate`.

  Column ordinals come from a window function rather than
  information_schema.columns.ordinal_position, which the server reports as 1 for
  every column. system.columns yields columns in definition order, so numbering
  the partition reproduces the real ordinal.
#}
{% macro tidbcloudlake__get_catalog(information_schema, schemas) -%}
  {%- set schema_filter -%}
    {%- for schema in schemas -%}
      '{{ schema }}'
      {%- if not loop.last %}, {% endif -%}
    {%- endfor -%}
  {%- endset -%}
  {%- call statement('catalog', fetch_result=True) -%}
    with cols as (
      select
        database as column_database,
        `table` as column_table,
        name as column_name,
        data_type as column_data_type,
        comment as column_comment,
        row_number() over (partition by database, `table`) as column_index
      from system.columns
      where database in ({{ schema_filter }})
    )
    select
      null as table_database,
      tables.database as table_schema,
      tables.name as table_name,
      tables.table_type as table_type,
      nullif(tables.comment, '') as table_comment,
      cols.column_name as column_name,
      cols.column_index as column_index,
      cols.column_data_type as column_type,
      nullif(cols.column_comment, '') as column_comment,
      tables.owner as table_owner
    from system.tables as tables
    join cols
      on cols.column_database = tables.database
     and cols.column_table = tables.name
    where tables.database != 'system'
      and tables.database in ({{ schema_filter }})
    order by tables.database, tables.name, cols.column_index
  {%- endcall -%}
  {{ return(load_result('catalog').table) }}
{%- endmacro %}
