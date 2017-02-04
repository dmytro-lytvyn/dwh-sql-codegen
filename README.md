# DWH SQL CodeGen

# Description

DWH SQL CodeGen is a cross-platform GUI application with a simple interface, built using Python and WxWidgets, that generates SQL scripts to build and load DWH (PostgreSQL/Redshift) from staging tables.

The application should be considered rather as a working prototype, and needs a lot of refactoring and cleaning up. Nevertheless, it's already useful in its current state, and saves the hours and days you can spend writing thousands of lines of SQL code.

The metadata of the DWH entities are stored in a small SQLite database, loaded on application's startup. If the metadata database is missing, the application creates an empty one from a source SQL script.

![DWH SQL CodeGen screenshot](https://dmytro-lytvyn.github.io/assets/dwh-sql-codegen/screenshot.png)

## DWH architecture

The DWH architecture is predefined and will be described in detail in a series of articles in my blog: https://dmytro-lytvyn.github.io. The brief overview is provided below.

Essentially, DWH tables represent entities, each loaded from a single staging table or a subquery (let's consider a typical customer dimension table: **stage.customer**). Every entity has a business key (one or more columns that uniquely identify a record of this entity in the source system - e.g. **customer_id**), and a surrogate key, representing it in the DWH, generated as a sequential number during the data loading process (e.g. **entity_key**). The foreign keys are enriched with surrogate keys of the referenced entities (for example, **address_id** and **address_id_key**).

Every loaded entity is represented as several tables in the DWH: Main table (containing all fields from a source table or query - e.g. **dw.dim_customer_main**), PK Lookup table (holding the correlation between a business key and a surrogate key - e.g. **dw.dim_customer_pk_lookup**), Batch Info table (with the metadata of the Batches that loaded the current versions of the corresponding entities - e.g. **dw.dim_customer_main_batch_info**), and a History table, which holds the previous versions of the changed rows and by structure is the same as Batch Info table and Main entity table, combined - e.g. **dw.dim_customer_main_history**.

## Basic functionality

The application allows to select the source tables and automatically loads their structure into the interface. Then you can select one or more fields as the Business Key, define which fields are the foreign keys to other tables, add custom fields (e.g. with calculated values). After that, you can already generate a DDL script to create the tables for your new entity, and an ETL script to populate them. The same ETL script can be scheduled to run daily or hourly - whenever you already have a new portion of data in the staging table.

You can choose, whether you want to track the deleted records or not. If you need to track the deleted records, your staging table must be a full snapshot of the source table, so that the ETL script can check, which rows are missing and mark them as deleted.

If you don't need to track the deleted records, the script will load the data incrementally (with or without tracking changes of already loaded entities, depending on the setting per entity), and it makes sense to have only the recently changed rows in the staging table. Usually the last 3 days of changes is enough - if something breaks during the weekend, you can still fix it on Monday and the missing data will be loaded automatically.

## Simple tutorial

Let's add one staging table **stage.customer** and create two entities in the DWH for it (**dw.dim_email_main** and **dw.dim_customer_main**).

```sql
create table stage.customer (
	customer_id bigint,
	date_created timestamp,
	date_updated timestamp,
	email varchar(255),
	first_name varchar(255),
	last_name varchar(255),
	is_enabled bool,
	additional_data json
	version integer
);
```

First, we need to add a new database. Click "Add Stage Db" and fill in the data. If you want the application to be able to connect to your database and fetch the tables structure, you can fill in the connection parameters (host, port, db name, user and password). Otherwise, just fill in and name for your staging database, and a schema name, where all temporary staging tables will be created in the scripts. Click "Save and refresh".

![Stage DB screenshot](https://dmytro-lytvyn.github.io/assets/dwh-sql-codegen/tutorial-stage-db.png)

Now we can add new tables. Let's create an Email entity, which will be used as a separate dimension, and load it from the **stage.customer** table. Click "Add Stage Table" button and populate the fields as shown below. We don't need to track changes or keep the history, because the only column we need is the key, so no other fields will be changed. If the email is changed, than it'll simply create a new record in **dw.dim_email_main**.

![Stage Email table screenshot](https://dmytro-lytvyn.github.io/assets/dwh-sql-codegen/tutorial-stage-email.png)

On the Columns level, we can just add one email column, but since we want it to serve as a key, we need to make it as unified as possible, so let's set "Column Expression" to `lower(trim(email))`, and mark this column as BK. We can specify the Ordinal Position of the columns in the target table with the increment of 10, so that later we can easily add new columns between them without renumbering all of them.

![Email columns screenshot](https://dmytro-lytvyn.github.io/assets/dwh-sql-codegen/tutorial-dim_email.png)

Now we can add the same table again, to load our **dw.dim_customer_main** from it. This time, we can do it automatically. Click the "Import Stage Table" button and select an existing **stage.customer** table from your database. Then, go to the level of Database in the tree and populate the missing column "Target Entity Schema". We can now set "Is Track Changes" and "Is Keep History" flags, because we want to track the changes done to customers in the source system. Then, click "Save and refresh" button.

![Stage Customer table screenshot](https://dmytro-lytvyn.github.io/assets/dwh-sql-codegen/tutorial-stage-customer.png)

On the Columns level, we now see all columns automatically added and numbered. We only need to set a Business Key for the entity (this time it's customer_id, of course), apply the same conversion to email column: `lower(trim(email))`, and then select for it FK Entity Name (dim_email).

![Customer columns screenshot](https://dmytro-lytvyn.github.io/assets/dwh-sql-codegen/tutorial-dim_customer.png)

Optionally, we can specify that this FK might contain inferred keys (*"Late Arriving Dimensions"*, in other words). If this option is checked, the script will add any keys, missing in the referenced FK table, to that table, and can also set one field (it should be the Business Key column, of course) to the value of the current column. The Inferred option is recommended, because it allows us not to worry about the order of loading the tables.

![Inferred columns screenshot](https://dmytro-lytvyn.github.io/assets/dwh-sql-codegen/tutorial-inferred.png)

We should also specify "Is Date Updated" flag for "date_updated" column, because it wil be used in the script to obtain the latest updated record with the same business key (if any). We can also set "Is Ignore Changes" flag for this field, because if no other fields are changed, we don't want to store a new record in the History table.

We can also add some more "derived" columns, for example extract values from JSON fields, convert dates from the text format, etc.

One or more columns can be completely ignored using "Is Ignored" flag, and they will not be loaded to the target table.
When all is done, we can generate the DDL scripts for each entity (Ctrl+D, or from the File menu), and ETL scripts (Ctrl+G, or from the File menu).

![Save ETL screenshot](https://dmytro-lytvyn.github.io/assets/dwh-sql-codegen/tutorial-save-etl.png)

The application doesn't write anything to the database - you can run the DDL scripts manually and schedule the ETL scripts to run daily, after your staging tables are loaded.
