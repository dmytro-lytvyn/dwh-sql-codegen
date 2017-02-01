create table project (
  project_id integer primary key,
  project_name text
);

create table stage_db (
  stage_db_id integer primary key,
  project_id integer,
  stage_db_name text,
  driver text,
  host text,
  port text,
  database text,
  user text,
  password text,
  staging_schema text,
  is_delete_temp_tables integer
);

create table stage_table (
  stage_table_id integer primary key,
  stage_db_id integer,
  schema_name text,
  table_name text,
  table_expression text,
  target_entity_schema text,
  target_entity_name text,
  target_entity_subname text
);

create table stage_column (
  stage_column_id integer primary key,
  stage_table_id integer,
  column_name text,
  column_expression text,
  column_type text,
  is_bk integer, -- is a part of current entity BK
  is_ignored integer,
  target_ordinal_pos integer,
  target_attribute_name text,
  target_attribute_type text,
  fk_entity_name text, -- is a BK of another entity
  is_fk_inferred integer,
  fk_entity_subname text, -- For inferred: subname of another entity (to populate a column in)
  fk_entity_attribute text, -- For inferred: populate this target entity attribute with current column value
  is_fk_mandatory integer,
  is_unix_timestamp integer,
  is_date_updated integer,
  target_distkey_pos integer,
  target_sortkey_pos integer
);
