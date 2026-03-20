-- ============================================================
-- DEB's Health Navigator — Seed Data
-- Initial data migrated from hardcoded JS arrays
-- Run AFTER schema.sql: psql -U <user> -d <dbname> -f seed.sql
-- ============================================================


-- ============================================================
-- DISEASES (from alerts.js diseaseColors + diseaseOutbreaks)
-- ============================================================
INSERT INTO diseases (name, common_names, category, description, symptoms, transmission_method, incubation_period, risk_factors, mortality_rate, seasonal_pattern, is_notifiable, icd_code)
VALUES
(
    'Dengue',
    ARRAY['dengue fever', 'break-bone fever'],
    'viral',
    'Dengue is a mosquito-borne tropical disease caused by the dengue virus (DENV). It is transmitted by Aedes mosquitoes, primarily Aedes aegypti.',
    'High fever (40°C/104°F), severe headache, pain behind the eyes, muscle and joint pains, nausea, vomiting, swollen glands, rash',
    'Bite of infected Aedes aegypti mosquito. No person-to-person transmission.',
    '4-10 days',
    'Living in or traveling to tropical/subtropical areas, prior dengue infection (increases risk of severe dengue), infants and young children',
    2.50,
    'Monsoon and post-monsoon season (Jul-Nov)',
    TRUE,
    'A97'
),
(
    'Malaria',
    ARRAY['ague', 'marsh fever'],
    'parasitic',
    'Malaria is a life-threatening disease caused by Plasmodium parasites transmitted through the bites of infected female Anopheles mosquitoes.',
    'Cyclic fever with chills and sweating, headache, muscle aches, fatigue, nausea and vomiting, diarrhea, anemia, jaundice',
    'Bite of infected female Anopheles mosquito. Can also be transmitted through blood transfusion or congenital transmission.',
    '7-30 days (P. falciparum: 9-14 days, P. vivax: 12-18 days)',
    'Residents of endemic areas, travelers to endemic regions, children under 5, pregnant women, people with low immunity',
    0.30,
    'Monsoon and post-monsoon season (Jun-Nov)',
    TRUE,
    'B54'
),
(
    'COVID-19',
    ARRAY['coronavirus disease 2019', 'SARS-CoV-2 infection'],
    'viral',
    'COVID-19 is an infectious disease caused by the SARS-CoV-2 virus. It primarily affects the respiratory system and can range from asymptomatic to severe illness.',
    'Fever, dry cough, fatigue, loss of taste or smell, shortness of breath, sore throat, nasal congestion, body aches, headache, diarrhea',
    'Respiratory droplets and aerosols from infected persons. Contact with contaminated surfaces (less common).',
    '1-14 days (average 5-6 days)',
    'Elderly (60+), people with chronic conditions (diabetes, heart disease, lung disease), immunocompromised individuals, unvaccinated populations',
    1.00,
    'Year-round with seasonal waves',
    TRUE,
    'U07.1'
),
(
    'Influenza',
    ARRAY['flu', 'seasonal flu', 'grippe'],
    'viral',
    'Influenza is a contagious respiratory illness caused by influenza viruses that infect the nose, throat, and sometimes the lungs.',
    'Sudden onset fever, cough, sore throat, runny nose, body aches, headache, chills, fatigue, sometimes vomiting and diarrhea',
    'Respiratory droplets from coughing, sneezing, or talking. Contact with contaminated surfaces.',
    '1-4 days (average 2 days)',
    'Children under 5, adults over 65, pregnant women, people with chronic medical conditions, healthcare workers',
    0.10,
    'Winter months (Nov-Feb in northern India)',
    FALSE,
    'J11'
),
(
    'Typhoid',
    ARRAY['typhoid fever', 'enteric fever'],
    'bacterial',
    'Typhoid fever is a life-threatening infection caused by the bacterium Salmonella typhi. It is usually spread through contaminated water or food.',
    'Sustained high fever (rising stepwise), weakness, stomach pain, headache, constipation or diarrhea, loss of appetite, rose-coloured spots on chest',
    'Fecal-oral route through contaminated water and food. Can be spread by carriers who harbor the bacteria.',
    '6-30 days (average 8-14 days)',
    'Areas with poor sanitation, travelers to endemic areas, children, people without access to clean water',
    1.00,
    'Summer and monsoon months (Apr-Sep)',
    TRUE,
    'A01.0'
),
(
    'Cholera',
    ARRAY['cholera infection', 'Vibrio cholerae infection'],
    'bacterial',
    'Cholera is an acute diarrheal infection caused by ingestion of food or water contaminated with Vibrio cholerae bacterium.',
    'Profuse watery diarrhea (rice-water stools), severe dehydration, vomiting, leg cramps, rapid heart rate, low blood pressure',
    'Fecal-oral route through contaminated water and food. Particularly in areas with inadequate water treatment and sanitation.',
    '12 hours to 5 days (average 2-3 days)',
    'Areas with poor sanitation, displaced populations, slum dwellers, children under 5, people with blood type O',
    1.00,
    'Monsoon and flood seasons (Jun-Oct)',
    TRUE,
    'A00'
)
ON CONFLICT (name) DO NOTHING;


-- ============================================================
-- DISEASE GUIDELINES — Prevention (from alerts.js preventionData)
-- ============================================================

-- Dengue prevention
INSERT INTO disease_guidelines (disease_id, guideline_type, title, content, steps, source)
SELECT d.id, 'prevention', 'Dengue Prevention Steps', 
    'Key prevention measures to protect against dengue fever.',
    '["Eliminate stagnant water around your home where mosquitoes breed", "Use mosquito repellent and wear long sleeves, especially during dawn and dusk", "Install or repair window and door screens to keep mosquitoes out", "Use mosquito nets while sleeping, especially for children and elderly", "Support community fogging and clean-up drives in your area"]'::jsonb,
    'NVBDCP'
FROM diseases d WHERE d.name = 'Dengue'
ON CONFLICT (disease_id, guideline_type, title) DO NOTHING;

-- Malaria prevention
INSERT INTO disease_guidelines (disease_id, guideline_type, title, content, steps, source)
SELECT d.id, 'prevention', 'Malaria Prevention Steps',
    'Key prevention measures to protect against malaria.',
    '["Sleep under insecticide-treated bed nets (ITNs) every night", "Take prescribed antimalarial prophylaxis if traveling to high-risk regions", "Wear protective clothing and use DEET-based repellents", "Clear stagnant water, puddles, and blocked drains near your home", "Seek immediate medical attention if you experience cyclic fever and chills"]'::jsonb,
    'NVBDCP'
FROM diseases d WHERE d.name = 'Malaria'
ON CONFLICT (disease_id, guideline_type, title) DO NOTHING;

-- COVID-19 prevention
INSERT INTO disease_guidelines (disease_id, guideline_type, title, content, steps, source)
SELECT d.id, 'prevention', 'COVID-19 Prevention Steps',
    'Key prevention measures to protect against COVID-19.',
    '["Stay up-to-date with recommended booster vaccinations", "Wear a well-fitted mask in crowded or poorly ventilated indoor spaces", "Wash hands frequently with soap for at least 20 seconds", "Maintain physical distancing in high-risk environments", "Isolate immediately and get tested if you develop respiratory symptoms"]'::jsonb,
    'MOHFW'
FROM diseases d WHERE d.name = 'COVID-19'
ON CONFLICT (disease_id, guideline_type, title) DO NOTHING;

-- Influenza prevention
INSERT INTO disease_guidelines (disease_id, guideline_type, title, content, steps, source)
SELECT d.id, 'prevention', 'Influenza Prevention Steps',
    'Key prevention measures to protect against seasonal influenza.',
    '["Get an annual flu vaccination before the start of each season", "Cover your mouth and nose when coughing or sneezing; use a tissue or elbow", "Avoid close contact with people who are visibly sick", "Disinfect frequently touched surfaces like doorknobs, phones, and keyboards", "Stay home from work or school when experiencing flu symptoms"]'::jsonb,
    'IDSP'
FROM diseases d WHERE d.name = 'Influenza'
ON CONFLICT (disease_id, guideline_type, title) DO NOTHING;

-- Typhoid prevention
INSERT INTO disease_guidelines (disease_id, guideline_type, title, content, steps, source)
SELECT d.id, 'prevention', 'Typhoid Prevention Steps',
    'Key prevention measures to protect against typhoid.',
    '["Drink only boiled or purified water; avoid untreated tap water or ice", "Eat freshly cooked food; avoid raw salads, peeled fruits from street stalls", "Wash hands thoroughly with soap before eating and after using the washroom", "Get a typhoid vaccination, especially before traveling to endemic regions", "Ensure proper sanitation and sewage disposal in your community"]'::jsonb,
    'WHO'
FROM diseases d WHERE d.name = 'Typhoid'
ON CONFLICT (disease_id, guideline_type, title) DO NOTHING;

-- Cholera prevention
INSERT INTO disease_guidelines (disease_id, guideline_type, title, content, steps, source)
SELECT d.id, 'prevention', 'Cholera Prevention Steps',
    'Key prevention measures to protect against cholera.',
    '["Drink only safe, treated, or boiled water; avoid street-served beverages", "Wash fruits, vegetables, and hands with clean water before eating", "Ensure food is cooked thoroughly and served hot", "Dispose of human waste safely and avoid open defecation", "Seek oral rehydration treatment immediately if severe diarrhea develops"]'::jsonb,
    'WHO'
FROM diseases d WHERE d.name = 'Cholera'
ON CONFLICT (disease_id, guideline_type, title) DO NOTHING;


-- ============================================================
-- OUTBREAKS (from alerts.js diseaseOutbreaks)
-- ============================================================

-- Dengue outbreaks
INSERT INTO outbreaks (disease_id, state, region_name, latitude, longitude, cases_reported, radius_meters, severity, status, reported_date, source)
SELECT d.id, s.state, s.region, s.lat, s.lon, s.cases, s.radius, 'severe', 'active', '2026-02-08', 'NVBDCP'
FROM diseases d,
(VALUES
    ('Karnataka',    'Karnataka',      12.9716,  77.5946,  1250, 80000),
    ('Tamil Nadu',   'Tamil Nadu',     13.0827,  80.2707,  980,  70000),
    ('Kerala',       'Kerala',         10.8505,  76.2711,  650,  60000),
    ('Maharashtra',  'Maharashtra',    19.0760,  72.8777,  1100, 75000)
) AS s(state, region, lat, lon, cases, radius)
WHERE d.name = 'Dengue'
ON CONFLICT (disease_id, state, district, reported_date) DO NOTHING;

-- Malaria outbreaks
INSERT INTO outbreaks (disease_id, state, region_name, latitude, longitude, cases_reported, radius_meters, severity, status, reported_date, source)
SELECT d.id, s.state, s.region, s.lat, s.lon, s.cases, s.radius, 'moderate', 'active', '2026-02-08', 'NVBDCP'
FROM diseases d,
(VALUES
    ('Odisha',       'Odisha',         20.9517,  85.0985,  890,  85000),
    ('Chhattisgarh', 'Chhattisgarh',   21.2787,  81.8661,  720,  70000),
    ('Jharkhand',    'Jharkhand',      23.6102,  85.2799,  540,  65000),
    ('West Bengal',  'West Bengal',    22.5726,  88.3639,  430,  55000)
) AS s(state, region, lat, lon, cases, radius)
WHERE d.name = 'Malaria'
ON CONFLICT (disease_id, state, district, reported_date) DO NOTHING;

-- COVID-19 outbreaks
INSERT INTO outbreaks (disease_id, state, region_name, latitude, longitude, cases_reported, radius_meters, severity, status, reported_date, source)
SELECT d.id, s.state, s.region, s.lat, s.lon, s.cases, s.radius, 'moderate', 'active', '2026-02-08', 'MOHFW'
FROM diseases d,
(VALUES
    ('Delhi',          'Delhi',          28.6139,  77.2090,  2100, 50000),
    ('Uttar Pradesh',  'Uttar Pradesh',  26.8467,  80.9462,  1850, 90000),
    ('Gujarat',        'Gujarat',        23.0225,  72.5714,  1320, 70000),
    ('Rajasthan',      'Rajasthan',      26.9124,  75.7873,  980,  75000)
) AS s(state, region, lat, lon, cases, radius)
WHERE d.name = 'COVID-19'
ON CONFLICT (disease_id, state, district, reported_date) DO NOTHING;

-- Influenza outbreaks
INSERT INTO outbreaks (disease_id, state, region_name, latitude, longitude, cases_reported, radius_meters, severity, status, reported_date, source)
SELECT d.id, s.state, s.region, s.lat, s.lon, s.cases, s.radius, 'low', 'active', '2026-02-08', 'IDSP'
FROM diseases d,
(VALUES
    ('Punjab',            'Punjab',            31.1471,  75.3412,  670,  60000),
    ('Haryana',           'Haryana',           29.0588,  76.0856,  540,  55000),
    ('Himachal Pradesh',  'Himachal Pradesh',  31.1048,  77.1734,  320,  50000)
) AS s(state, region, lat, lon, cases, radius)
WHERE d.name = 'Influenza'
ON CONFLICT (disease_id, state, district, reported_date) DO NOTHING;

-- Typhoid outbreaks
INSERT INTO outbreaks (disease_id, state, region_name, latitude, longitude, cases_reported, radius_meters, severity, status, reported_date, source)
SELECT d.id, s.state, s.region, s.lat, s.lon, s.cases, s.radius, 'moderate', 'active', '2026-02-08', 'IDSP'
FROM diseases d,
(VALUES
    ('Bihar',           'Bihar',           25.0961,  85.3131,  780,  70000),
    ('Madhya Pradesh',  'Madhya Pradesh',  23.2599,  77.4126,  620,  80000),
    ('Assam',           'Assam',           26.2006,  92.9376,  450,  65000)
) AS s(state, region, lat, lon, cases, radius)
WHERE d.name = 'Typhoid'
ON CONFLICT (disease_id, state, district, reported_date) DO NOTHING;

-- Cholera outbreaks
INSERT INTO outbreaks (disease_id, state, region_name, latitude, longitude, cases_reported, radius_meters, severity, status, reported_date, source)
SELECT d.id, s.state, s.region, s.lat, s.lon, s.cases, s.radius, 'low', 'active', '2026-02-08', 'NCDC'
FROM diseases d,
(VALUES
    ('Andhra Pradesh', 'Andhra Pradesh', 15.9129,  79.7400,  340,  60000),
    ('Telangana',      'Telangana',      17.3850,  78.4867,  280,  55000)
) AS s(state, region, lat, lon, cases, radius)
WHERE d.name = 'Cholera'
ON CONFLICT (disease_id, state, district, reported_date) DO NOTHING;


-- ============================================================
-- TRENDS (from alerts.js trendsData — last 6 months)
-- ============================================================

-- Helper: insert trends for each disease across 6 months
INSERT INTO trends (disease_id, period_type, period_start, period_end, cases_count, growth_rate, source)
SELECT d.id, 'monthly', s.p_start::date, s.p_end::date, s.cases,
    CASE WHEN s.prev_cases > 0 THEN ROUND(((s.cases - s.prev_cases)::decimal / s.prev_cases) * 100, 2) ELSE NULL END,
    'IDSP'
FROM diseases d,
(VALUES
    -- Dengue
    ('Dengue', '2025-09-01', '2025-09-30', 850,  0),
    ('Dengue', '2025-10-01', '2025-10-31', 920,  850),
    ('Dengue', '2025-11-01', '2025-11-30', 1050, 920),
    ('Dengue', '2025-12-01', '2025-12-31', 1180, 1050),
    ('Dengue', '2026-01-01', '2026-01-31', 1320, 1180),
    ('Dengue', '2026-02-01', '2026-02-28', 1250, 1320),
    -- Malaria
    ('Malaria', '2025-09-01', '2025-09-30', 650,  0),
    ('Malaria', '2025-10-01', '2025-10-31', 720,  650),
    ('Malaria', '2025-11-01', '2025-11-30', 780,  720),
    ('Malaria', '2025-12-01', '2025-12-31', 820,  780),
    ('Malaria', '2026-01-01', '2026-01-31', 890,  820),
    ('Malaria', '2026-02-01', '2026-02-28', 720,  890),
    -- COVID-19
    ('COVID-19', '2025-09-01', '2025-09-30', 2800, 0),
    ('COVID-19', '2025-10-01', '2025-10-31', 2500, 2800),
    ('COVID-19', '2025-11-01', '2025-11-30', 2200, 2500),
    ('COVID-19', '2025-12-01', '2025-12-31', 2100, 2200),
    ('COVID-19', '2026-01-01', '2026-01-31', 2050, 2100),
    ('COVID-19', '2026-02-01', '2026-02-28', 2100, 2050),
    -- Influenza
    ('Influenza', '2025-09-01', '2025-09-30', 420,  0),
    ('Influenza', '2025-10-01', '2025-10-31', 480,  420),
    ('Influenza', '2025-11-01', '2025-11-30', 550,  480),
    ('Influenza', '2025-12-01', '2025-12-31', 620,  550),
    ('Influenza', '2026-01-01', '2026-01-31', 670,  620),
    ('Influenza', '2026-02-01', '2026-02-28', 540,  670),
    -- Typhoid
    ('Typhoid', '2025-09-01', '2025-09-30', 580,  0),
    ('Typhoid', '2025-10-01', '2025-10-31', 620,  580),
    ('Typhoid', '2025-11-01', '2025-11-30', 680,  620),
    ('Typhoid', '2025-12-01', '2025-12-31', 720,  680),
    ('Typhoid', '2026-01-01', '2026-01-31', 780,  720),
    ('Typhoid', '2026-02-01', '2026-02-28', 620,  780),
    -- Cholera
    ('Cholera', '2025-09-01', '2025-09-30', 280,  0),
    ('Cholera', '2025-10-01', '2025-10-31', 310,  280),
    ('Cholera', '2025-11-01', '2025-11-30', 340,  310),
    ('Cholera', '2025-12-01', '2025-12-31', 360,  340),
    ('Cholera', '2026-01-01', '2026-01-31', 380,  360),
    ('Cholera', '2026-02-01', '2026-02-28', 340,  380)
) AS s(disease_name, p_start, p_end, cases, prev_cases)
WHERE d.name = s.disease_name
ON CONFLICT (disease_id, state, district, period_type, period_start) DO NOTHING;


-- ============================================================
-- EDUCATION RESOURCES (from education.js videosData + blogsData + schemesData)
-- ============================================================

-- Videos
INSERT INTO education_resources (title, resource_type, url, embed_url, thumbnail_url, duration, disease_tags, content_tags, source, language)
VALUES
('Dengue: Symptoms and Prevention', 'video', 'https://www.youtube.com/watch?v=JPm7s5VwHkQ', 'https://www.youtube.com/embed/JPm7s5VwHkQ', 'https://img.youtube.com/vi/JPm7s5VwHkQ/hqdefault.jpg', '6:12', ARRAY['dengue'], ARRAY['symptoms','prevention'], 'YouTube', 'en'),
('Malaria Basics for Everyone', 'video', 'https://www.youtube.com/watch?v=_qzM3GeqvT0', 'https://www.youtube.com/embed/_qzM3GeqvT0', 'https://img.youtube.com/vi/_qzM3GeqvT0/hqdefault.jpg', '8:03', ARRAY['malaria'], ARRAY['overview'], 'YouTube', 'en'),
('Understanding Tuberculosis', 'video', 'https://www.youtube.com/watch?v=2VZkE0e2d6o', 'https://www.youtube.com/embed/2VZkE0e2d6o', 'https://img.youtube.com/vi/2VZkE0e2d6o/hqdefault.jpg', '7:40', ARRAY['tuberculosis'], ARRAY['treatment','awareness'], 'YouTube', 'en'),
('COVID-19 Prevention Guide', 'video', 'https://www.youtube.com/watch?v=BtN-goy9VOY', 'https://www.youtube.com/embed/BtN-goy9VOY', 'https://img.youtube.com/vi/BtN-goy9VOY/hqdefault.jpg', '9:57', ARRAY['covid'], ARRAY['prevention'], 'YouTube', 'en'),
('Type 2 Diabetes: What to Know', 'video', 'https://www.youtube.com/watch?v=wZAjVQWbMlE', 'https://www.youtube.com/embed/wZAjVQWbMlE', 'https://img.youtube.com/vi/wZAjVQWbMlE/hqdefault.jpg', '10:20', ARRAY['diabetes'], ARRAY['lifestyle'], 'YouTube', 'en'),
('Seasonal Flu Facts', 'video', 'https://www.youtube.com/watch?v=2RdWwZ2FhAE', 'https://www.youtube.com/embed/2RdWwZ2FhAE', 'https://img.youtube.com/vi/2RdWwZ2FhAE/hqdefault.jpg', '5:30', ARRAY['influenza'], ARRAY['prevention'], 'YouTube', 'en')
ON CONFLICT (url) DO NOTHING;

-- Blogs
INSERT INTO education_resources (title, resource_type, url, disease_tags, content_tags, excerpt, source, language)
VALUES
('Dengue Prevention Checklist', 'blog', 'https://www.who.int/news-room/fact-sheets/detail/dengue-and-severe-dengue', ARRAY['dengue'], ARRAY['prevention'], 'Complete guide to preventing dengue fever in your community.', 'WHO', 'en'),
('How to Use Mosquito Repellents Safely', 'blog', 'https://www.cdc.gov/mosquitoes/prevention/index.html', ARRAY['dengue','malaria'], ARRAY['guide'], 'Safety tips for using mosquito repellents effectively.', 'CDC', 'en'),
('Diabetes Diet Do''s and Don''ts', 'blog', 'https://www.diabetes.org/healthy-living/recipes-nutrition', ARRAY['diabetes'], ARRAY['lifestyle'], 'Nutritional guidelines for managing diabetes.', 'ADA', 'en'),
('Understanding TB Tests', 'blog', 'https://www.cdc.gov/tb/topic/testing/default.htm', ARRAY['tuberculosis'], ARRAY['testing'], 'Learn about different tuberculosis testing methods.', 'CDC', 'en'),
('COVID-19 Vaccine Information', 'blog', 'https://www.who.int/emergencies/diseases/novel-coronavirus-2019/covid-19-vaccines', ARRAY['covid'], ARRAY['vaccines'], 'Everything you need to know about COVID-19 vaccines.', 'WHO', 'en')
ON CONFLICT (url) DO NOTHING;

-- Government Schemes
INSERT INTO education_resources (title, resource_type, url, disease_tags, content_tags, excerpt, source, language)
VALUES
('Ayushman Bharat - Pradhan Mantri Jan Arogya Yojana', 'scheme', 'https://pmjay.gov.in/', ARRAY[]::TEXT[], ARRAY['insurance','healthcare'], 'Free health insurance coverage up to ₹5 lakh per family per year.', 'Government of India', 'en'),
('Janani Suraksha Yojana (JSY)', 'scheme', 'https://nhm.gov.in/index1.php?lang=1&level=3&sublinkid=841&lid=309', ARRAY[]::TEXT[], ARRAY['maternal','healthcare'], 'Cash assistance for pregnant women to promote institutional delivery.', 'NHM', 'en'),
('Rashtriya Bal Swasthya Karyakram (RBSK)', 'scheme', 'https://nhm.gov.in/index1.php?lang=1&level=3&sublinkid=1154&lid=604', ARRAY[]::TEXT[], ARRAY['child','healthcare'], 'Early detection and management of health conditions in children.', 'NHM', 'en'),
('Mission Indradhanush', 'scheme', 'https://www.nhp.gov.in/mission-indradhanush1_pg', ARRAY[]::TEXT[], ARRAY['vaccination','immunization'], 'Immunization program to cover all children and pregnant women.', 'Government of India', 'en')
ON CONFLICT (url) DO NOTHING;


-- ============================================================
-- DISEASE GUIDELINES — First Aid (from emergency.js firstAidDatabase)
-- ============================================================

-- First aid data (chest pain, bleeding, seizure, etc.) from emergency.js is
-- condition-based, not disease-based. These will be migrated when building
-- the backend API for emergency. Consider a separate `first_aid_guides` table
-- or making disease_id nullable in disease_guidelines if needed later.

-- NOTE: First aid data (chest pain, bleeding, seizure, etc.) from emergency.js is
-- condition-based, not disease-based. Consider a separate `first_aid_guides` table
-- or make disease_id nullable in disease_guidelines if needed later.
