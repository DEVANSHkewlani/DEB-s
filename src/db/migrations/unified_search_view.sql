DROP VIEW IF EXISTS unified_search_index CASCADE;

CREATE VIEW unified_search_index AS
SELECT 
    ('guideline_' || id::text)::varchar AS id,
    title::varchar(500),
    content::text,
    source::varchar(200),
    source_url::text
FROM disease_guidelines
UNION ALL
SELECT 
    ('outbreak_' || o.id::text)::varchar AS id,
    (d.name || ' Outbreak in ' || o.district || ', ' || o.state)::varchar(500) AS title,
    ('Reported ' || o.cases_reported || ' cases and ' || o.deaths_reported || ' deaths of ' || d.name || ' on ' || o.reported_date || '. Severity is ' || o.severity)::text AS content,
    o.source::varchar(200),
    o.source_url::text
FROM outbreaks o
JOIN diseases d ON o.disease_id = d.id
UNION ALL
SELECT 
    ('trend_' || t.id::text)::varchar AS id,
    (d.name || ' Trends in ' || t.district || ', ' || t.state)::varchar(500) AS title,
    ('Recorded ' || t.cases_count || ' case instances of ' || d.name || ' for period ' || t.period_start || '-' || t.period_end)::text AS content,
    t.source::varchar(200),
    t.source_url::text
FROM trends t
JOIN diseases d ON t.disease_id = d.id
UNION ALL
SELECT 
    ('medicine_' || m.id::text)::varchar AS id,
    ('Medicine: ' || m.brand_name || ' (' || mn.name || ')')::varchar(500) AS title,
    ('Dosage Form: ' || m.dosage_form || ', Strength: ' || m.strength || ', Manufacturer: ' || m.manufacturer || ', Schedule: ' || m.schedule)::text AS content,
    m.source::varchar(200),
    m.source_url::text
FROM medicines m
JOIN medicine_names mn ON m.generic_id = mn.id
UNION ALL
SELECT 
    'education_' || id::text AS id,
    title::varchar(500) AS title,
    (COALESCE(excerpt, '') || ' ' || COALESCE(summary, ''))::text AS content,
    source::varchar(200) AS source,
    url::text AS source_url
FROM education_resources
UNION ALL
SELECT 
    'disease_' || id::text AS id,
    name::varchar(500) AS title,
    (COALESCE(description, '') || ' Symptoms: ' || COALESCE(symptoms, ''))::text AS content,
    'Internal Registry'::varchar(200) AS source,
    NULL::text AS source_url
FROM diseases;
