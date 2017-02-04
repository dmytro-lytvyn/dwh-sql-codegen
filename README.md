# dwh-sql-codegen

DWH SQL CodeGen is a GUI application with a simple interface, built using Python and WxWidgets, that generates SQL scripts to build and load DWH (PostgreSQL/Redshift) from staging tables.

The application should be considered rather as a working prototype, and needs a lot of refactoring and cleaning up. Nevertheless, it's already useful in its current state, and saves the hours and days you can spend writing thousands of lines of SQL code.

The metadata of the DWH entities are stored in a small SQLite database, loaded on application's startup. If the metadata database is missing, the application creates an empty one from a source SQL script.

The DWH architecture is predefined and will be described in detail in a series of articles in my blog: https://dmytro-lytvyn.github.io. The brief overview is provided below.

Essentially, DWH tables represent entities, each loaded from a single staging table or a subquery (we'll use a typical customer dimension table: stage.customer). Every entity has a business key (one or more columns that uniquely identify a record of this entity in the source system - e.g. customer_id), and a surrogate key, representing it in the DWH, generated as a sequential number during the data loading process (entity_key). The foreign keys are enriched with surrogate keys of the referenced entities (for example, address_id and address_id_key).

Every loaded entity is represented as several tables in the DWH: Main table (containing all fields from a source table or query - e.g. dw.dim_customer_main), PK Lookup table (holding the correlation between Business Key and Surrogate Key - e.g. dw.dim_customer_pk_lookup), Batch Info table (with the metadata of the Batches that loaded the current versions of the corresponding entities - e.g. dw.dim_customer_main_batch_info), and a History table, which holds the previous versions of the changed rows and by structure is the same as Batch Info table and Main entity table, combined - e.g. dw.dim_customer_main_history.

The application allows to select the source tables and automatically loads their structure into the interface. Then you can select one or more fields as the Business Key, define which fields are the foreign keys to other tables, add custom fields (e.g. with calculated values). After that, you can already generate a DDL script to create the tables for your new entity, and an ETL script to populate them. The same ETL script can be scheduled to run daily or hourly - whenever you already have a new portion of data in the staging table.

You can choose, whether you want to track the deleted records or not. If you need to track the deleted records, your staging table must be a full snapshot of the source table, so that the ETL script can check, which rows are missing and mark them as deleted.

If you don't need to track the deleted records, the script will load the data incrementally (with or without tracking changes of already loaded entities, depending on the setting per entity), and it makes sense to have only the recently changed rows in the staging table. Usually the last 3 days of changes is enough - if something breaks during the weekend, you can still fix it on Monday and the missing data will be loaded automatically.
