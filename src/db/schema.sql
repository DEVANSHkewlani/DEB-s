-- ============================================================
-- DEB's Health Navigator — PostgreSQL Schema
-- 14 tables + indexes + extensions
-- Run: psql -U <user> -d <dbname> -f schema.sql
-- ============================================================
-- Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
-- NOTE: pgvector required for production embeddings. Install with:
--   CREATE EXTENSION IF NOT EXISTS "pgvector";
-- Then run the ALTER TABLE statements at the bottom of this file.
-- ============================================================
-- 1. diseases — Master disease registry
-- ============================================================
CREATE TABLE IF NOT EXISTS diseases (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) UNIQUE NOT NULL,
    common_names TEXT [],
    -- aliases like "break-bone fever"
    category VARCHAR(50) NOT NULL,
    -- viral, bacterial, parasitic, fungal, prion, other
    description TEXT,
    symptoms TEXT,
    transmission_method TEXT,
    incubation_period VARCHAR(100),
    -- e.g., "4-10 days"
    risk_factors TEXT,
    mortality_rate DECIMAL(5, 2),
    -- percentage
    affected_demographics TEXT,
    seasonal_pattern VARCHAR(200),
    -- e.g., "Monsoon (Jul-Oct)"
    is_notifiable BOOLEAN DEFAULT FALSE,
    icd_code VARCHAR(20),
    -- ICD-10/11 code
    source_urls TEXT [],
    -- where data was sourced
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
-- ============================================================
-- 2. disease_guidelines — Prevention, symptoms, treatment, etc.
-- ============================================================
CREATE TABLE IF NOT EXISTS disease_guidelines (
    id SERIAL PRIMARY KEY,
    disease_id INTEGER NOT NULL REFERENCES diseases(id) ON DELETE CASCADE,
    guideline_type VARCHAR(50) NOT NULL,
    -- prevention, symptoms, treatment, diagnosis, faq, first_aid
    title VARCHAR(500) NOT NULL,
    content TEXT NOT NULL,
    steps JSONB,
    -- ordered steps array if applicable
    source VARCHAR(200),
    -- WHO, MoHFW, CDC, etc.
    source_url TEXT,
    language VARCHAR(10) DEFAULT 'en',
    embedding TEXT,
    -- JSON array; upgrade to VECTOR(1024) with pgvector
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (disease_id, guideline_type, title)
);
-- ============================================================
-- 3. outbreaks — Geographic outbreak data for alerts map
-- ============================================================
CREATE TABLE IF NOT EXISTS outbreaks (
    id SERIAL PRIMARY KEY,
    disease_id INTEGER NOT NULL REFERENCES diseases(id) ON DELETE CASCADE,
    state VARCHAR(100) NOT NULL,
    -- Indian state
    district VARCHAR(100),
    region_name VARCHAR(200),
    -- human-readable label
    latitude DECIMAL(10, 7) NOT NULL,
    longitude DECIMAL(10, 7) NOT NULL,
    cases_reported INTEGER DEFAULT 0,
    deaths_reported INTEGER DEFAULT 0,
    recovered INTEGER DEFAULT 0,
    radius_meters INTEGER,
    -- affected area for map circle
    severity VARCHAR(20) DEFAULT 'moderate',
    -- low, moderate, severe, critical
    status VARCHAR(20) DEFAULT 'active',
    -- active, contained, resolved
    reported_date DATE NOT NULL,
    source VARCHAR(200),
    source_url TEXT,
    bulletin_id VARCHAR(100),
    -- IDSP/WHO bulletin reference
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (disease_id, state, district, reported_date)
);
-- ============================================================
-- 4. trends — Time-series disease data for charts
-- ============================================================
CREATE TABLE IF NOT EXISTS trends (
    id SERIAL PRIMARY KEY,
    disease_id INTEGER NOT NULL REFERENCES diseases(id) ON DELETE CASCADE,
    state VARCHAR(100),
    -- NULL = national level
    district VARCHAR(100),
    period_type VARCHAR(10) NOT NULL,
    -- weekly, monthly
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    cases_count INTEGER DEFAULT 0,
    deaths_count INTEGER DEFAULT 0,
    recovery_count INTEGER DEFAULT 0,
    growth_rate DECIMAL(8, 2),
    -- % change from previous period
    source VARCHAR(200),
    source_url TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (
        disease_id,
        state,
        district,
        period_type,
        period_start
    )
);
-- ============================================================
-- 5. medicine_names — Master registry of generic drugs
-- ============================================================
CREATE TABLE IF NOT EXISTS medicine_names (
    id SERIAL PRIMARY KEY,
    name VARCHAR(300) UNIQUE NOT NULL,
    -- Generic name
    drug_class VARCHAR(200),
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
-- ============================================================
-- 6. medicines — Specific formulations / brand names
-- ============================================================
CREATE TABLE IF NOT EXISTS medicines (
    id SERIAL PRIMARY KEY,
    generic_id INTEGER NOT NULL REFERENCES medicine_names(id) ON DELETE CASCADE,
    brand_name VARCHAR(300),
    manufacturer VARCHAR(300),
    dosage_form VARCHAR(100),
    strength VARCHAR(100),
    schedule VARCHAR(50),
    source VARCHAR(200),
    source_url TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (generic_id, brand_name, dosage_form, strength)
);
-- ============================================================
-- 7. education_resources — Videos, blogs, schemes, articles
-- ============================================================
CREATE TABLE IF NOT EXISTS education_resources (
    id SERIAL PRIMARY KEY,
    title VARCHAR(500) NOT NULL,
    resource_type VARCHAR(20) NOT NULL,
    -- video, blog, scheme, article, infographic
    url TEXT UNIQUE NOT NULL,
    -- dedup key
    embed_url TEXT,
    -- for YouTube embeds
    thumbnail_url TEXT,
    duration VARCHAR(20),
    -- for videos e.g. "6:12"
    disease_tags TEXT [],
    -- ["dengue", "malaria"]
    content_tags TEXT [],
    -- ["prevention", "symptoms"]
    excerpt TEXT,
    summary TEXT,
    -- AI-generated, stored
    source VARCHAR(200),
    language VARCHAR(10) DEFAULT 'en',
    embedding TEXT,
    -- JSON array; upgrade to VECTOR(1024) with pgvector
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
-- ============================================================
-- 6. emergency_logs — Emergency requests with location
-- ============================================================
CREATE TABLE IF NOT EXISTS emergency_logs (
    id SERIAL PRIMARY KEY,
    emergency_type VARCHAR(30) NOT NULL,
    -- ambulance, medicine, doctor
    condition_described TEXT,
    -- raw user input
    matched_condition VARCHAR(50),
    -- first-aid key match
    severity VARCHAR(20),
    -- low, moderate, severe, critical
    latitude DECIMAL(10, 7),
    longitude DECIMAL(10, 7),
    state VARCHAR(100),
    -- reverse-geocoded
    district VARCHAR(100),
    nearest_hospital_name VARCHAR(300),
    nearest_hospital_distance_m DECIMAL(10, 1),
    -- meters
    nearest_hospital_phone VARCHAR(30),
    created_at TIMESTAMPTZ DEFAULT NOW()
);
-- ============================================================
-- 7. connect_cache_doctors — OSM cache for doctors/clinics
-- ============================================================
CREATE TABLE IF NOT EXISTS connect_cache_doctors (
    id SERIAL PRIMARY KEY,
    osm_id BIGINT UNIQUE NOT NULL,
    name VARCHAR(300),
    amenity_type VARCHAR(50),
    -- doctors, clinic
    speciality VARCHAR(200),
    latitude DECIMAL(10, 7) NOT NULL,
    longitude DECIMAL(10, 7) NOT NULL,
    phone VARCHAR(50),
    email VARCHAR(200),
    website TEXT,
    address TEXT,
    opening_hours VARCHAR(300),
    city VARCHAR(100),
    state VARCHAR(100),
    cached_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL -- cached_at + 24h
);
-- ============================================================
-- 8. connect_cache_hospitals — OSM cache for hospitals
-- ============================================================
CREATE TABLE IF NOT EXISTS connect_cache_hospitals (
    id SERIAL PRIMARY KEY,
    osm_id BIGINT UNIQUE NOT NULL,
    name VARCHAR(300),
    amenity_type VARCHAR(50),
    -- hospital
    speciality VARCHAR(200),
    latitude DECIMAL(10, 7) NOT NULL,
    longitude DECIMAL(10, 7) NOT NULL,
    phone VARCHAR(50),
    email VARCHAR(200),
    website TEXT,
    address TEXT,
    opening_hours VARCHAR(300),
    city VARCHAR(100),
    state VARCHAR(100),
    cached_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL
);
-- ============================================================
-- 9. connect_cache_pharmacies — OSM cache for pharmacies
-- ============================================================
CREATE TABLE IF NOT EXISTS connect_cache_pharmacies (
    id SERIAL PRIMARY KEY,
    osm_id BIGINT UNIQUE NOT NULL,
    name VARCHAR(300),
    amenity_type VARCHAR(50),
    -- pharmacy
    speciality VARCHAR(200),
    latitude DECIMAL(10, 7) NOT NULL,
    longitude DECIMAL(10, 7) NOT NULL,
    phone VARCHAR(50),
    email VARCHAR(200),
    website TEXT,
    address TEXT,
    opening_hours VARCHAR(300),
    city VARCHAR(100),
    state VARCHAR(100),
    cached_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL
);
-- ============================================================
-- 10. user_reports — Community health reports
-- ============================================================
CREATE TABLE IF NOT EXISTS user_reports (
    id SERIAL PRIMARY KEY,
    report_type VARCHAR(20) NOT NULL,
    -- personal, regional, outbreak, other
    location VARCHAR(300) NOT NULL,
    latitude DECIMAL(10, 7),
    -- if geocoded
    longitude DECIMAL(10, 7),
    onset_date DATE,
    severity VARCHAR(20) DEFAULT 'unknown',
    -- unknown, mild, moderate, severe
    people_affected INTEGER,
    details TEXT NOT NULL,
    reporter_name VARCHAR(200),
    -- optional
    reporter_contact VARCHAR(200),
    -- optional
    consent BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
-- ============================================================
-- 11. scraper_logs — Scraper run tracking
-- ============================================================
CREATE TABLE IF NOT EXISTS scraper_logs (
    id SERIAL PRIMARY KEY,
    source_name VARCHAR(100) NOT NULL,
    -- IDSP, WHO, CDC, etc.
    source_url TEXT,
    scrape_type VARCHAR(30),
    -- diseases, outbreaks, trends, guidelines, education
    status VARCHAR(20) NOT NULL,
    -- success, failed, partial
    records_found INTEGER DEFAULT 0,
    records_inserted INTEGER DEFAULT 0,
    records_updated INTEGER DEFAULT 0,
    records_skipped INTEGER DEFAULT 0,
    error_message TEXT,
    duration_ms INTEGER,
    started_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ
);
-- ============================================================
-- 12. chat_sessions — Chat session management
-- ============================================================
CREATE TABLE IF NOT EXISTS chat_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title VARCHAR(255),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 13. chat_history — Session-based conversation logs
-- ============================================================
CREATE TABLE IF NOT EXISTS chat_history (
    id SERIAL PRIMARY KEY,
    session_id UUID NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    role VARCHAR(10) NOT NULL,
    -- user, assistant, system
    content TEXT NOT NULL,
    language VARCHAR(10) DEFAULT 'en',
    was_answerable BOOLEAN DEFAULT TRUE,
    -- false → knowledge_gap created
    created_at TIMESTAMPTZ DEFAULT NOW()
);
-- ============================================================
-- 13. knowledge_gaps — Unified gap tracking
-- ============================================================
CREATE TABLE IF NOT EXISTS knowledge_gaps (
    id SERIAL PRIMARY KEY,
    gap_type VARCHAR(30) NOT NULL,
    -- chatbot_unanswered, missing_education, emergency_cluster
    query_text TEXT,
    -- unanswered question or missing topic
    related_disease VARCHAR(200),
    location VARCHAR(300),
    -- for emergency clusters
    latitude DECIMAL(10, 7),
    longitude DECIMAL(10, 7),
    occurrence_count INTEGER DEFAULT 1,
    status VARCHAR(20) DEFAULT 'open',
    -- open, in_progress, resolved
    resolved_at TIMESTAMPTZ,
    resolution_source TEXT,
    -- e.g. "scraper_run_456"
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
-- ============================================================
-- 14. unified_search_index — View for RAG keyword search
-- ============================================================
CREATE OR REPLACE VIEW unified_search_index AS
SELECT 'disease_' || id::text as id, name as title, description as content, 'disease' as type, name as disease_name, 'WHO/MedlinePlus' as source, 'https://medlineplus.gov' as source_url FROM diseases
UNION ALL
SELECT 'guideline_' || id::text as id, title, content, 'guideline' as type, (SELECT name FROM diseases WHERE id = disease_id) as disease_name, source, source_url FROM disease_guidelines
UNION ALL
SELECT 'resource_' || id::text as id, title, excerpt as content, 'resource' as type, (SELECT name FROM diseases WHERE name = ANY(disease_tags) LIMIT 1) as disease_name, source, url as source_url FROM education_resources;

-- ============================================================
-- INDEXES
-- ============================================================
-- diseases
CREATE INDEX idx_diseases_name ON diseases(name);
CREATE INDEX idx_diseases_category ON diseases(category);
-- disease_guidelines
CREATE INDEX idx_guidelines_disease ON disease_guidelines(disease_id);
CREATE INDEX idx_guidelines_type ON disease_guidelines(guideline_type);
-- outbreaks
CREATE INDEX idx_outbreaks_disease ON outbreaks(disease_id);
CREATE INDEX idx_outbreaks_state ON outbreaks(state);
CREATE INDEX idx_outbreaks_status ON outbreaks(status);
CREATE INDEX idx_outbreaks_date ON outbreaks(reported_date DESC);
CREATE INDEX idx_outbreaks_coords ON outbreaks(latitude, longitude);
-- trends
CREATE INDEX idx_trends_disease_period ON trends(disease_id, period_start DESC);
CREATE INDEX idx_trends_state ON trends(state);
-- medicines
CREATE INDEX idx_medicine_names ON medicine_names(name);
CREATE INDEX idx_medicines_generic ON medicines(generic_id);
CREATE INDEX idx_medicines_brand ON medicines(brand_name);
-- emergency_logs
CREATE INDEX idx_emergency_condition ON emergency_logs(matched_condition);
CREATE INDEX idx_emergency_coords ON emergency_logs(latitude, longitude);
CREATE INDEX idx_emergency_time ON emergency_logs(created_at DESC);
-- connect cache expiry
CREATE INDEX idx_cache_doctors_expires ON connect_cache_doctors(expires_at);
CREATE INDEX idx_cache_hospitals_expires ON connect_cache_hospitals(expires_at);
CREATE INDEX idx_cache_pharmacies_expires ON connect_cache_pharmacies(expires_at);
-- chat_history
CREATE INDEX idx_chat_session ON chat_history(session_id, created_at);
-- knowledge_gaps
CREATE INDEX idx_knowledge_gaps_status ON knowledge_gaps(status);
CREATE INDEX idx_knowledge_gaps_type ON knowledge_gaps(gap_type);
-- scraper_logs
CREATE INDEX idx_scraper_source ON scraper_logs(source_name, started_at DESC);
-- ============================================================
-- UPDATED_AT TRIGGER (auto-update updated_at column)
-- ============================================================
CREATE OR REPLACE FUNCTION update_updated_at() RETURNS TRIGGER AS $$ BEGIN NEW.updated_at = NOW();
RETURN NEW;
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER trg_diseases_updated BEFORE
UPDATE ON diseases FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER trg_guidelines_updated BEFORE
UPDATE ON disease_guidelines FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER trg_outbreaks_updated BEFORE
UPDATE ON outbreaks FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER trg_education_updated BEFORE
UPDATE ON education_resources FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER trg_knowledge_gaps_updated BEFORE
UPDATE ON knowledge_gaps FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER trg_chat_sessions_updated BEFORE
UPDATE ON chat_sessions FOR EACH ROW EXECUTE FUNCTION update_updated_at();
-- ============================================================
-- PGVECTOR UPGRADE (run after installing pgvector extension)
-- ============================================================
-- CREATE EXTENSION IF NOT EXISTS "pgvector";
-- ALTER TABLE disease_guidelines ALTER COLUMN embedding TYPE VECTOR(1024) USING embedding::VECTOR(1024);
-- ALTER TABLE education_resources ALTER COLUMN embedding TYPE VECTOR(1024) USING embedding::VECTOR(1024);