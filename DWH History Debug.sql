-- DWH History Debug
select h.* from dwh.dim_entity_name_history h
where h.entity_uuid in (select entity_uuid from dwh.dim_entity_name_metadata where is_deleted = 1)
union all
select m.*, null as batch_time_to, null as batch_uuid_to, t.*
from dwh.dim_entity_name_metadata m
	left join dwh.dim_entity_name t on t.entity_uuid = m.entity_uuid
where m.entity_uuid in (select entity_uuid from dwh.dim_entity_name_metadata where is_deleted = 1)
order by 1, 4
;