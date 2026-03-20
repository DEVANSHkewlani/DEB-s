INSERT INTO knowledge_gaps (
    id,
    gap_type,
    query_text,
    related_disease,
    location,
    latitude,
    longitude,
    occurrence_count,
    status,
    resolved_at,
    resolution_source,
    created_at,
    updated_at
  )
VALUES (
    id :integer,
    'gap_type:character varying',
    'query_text:text',
    'related_disease:character varying',
    'location:character varying',
    latitude :numeric,
    longitude :numeric,
    occurrence_count :integer,
    'status:character varying',
    'resolved_at:timestamp with time zone',
    'resolution_source:text',
    'created_at:timestamp with time zone',
    'updated_at:timestamp with time zone'
  );