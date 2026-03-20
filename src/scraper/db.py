import time
import psycopg2
from psycopg2.extras import execute_values
from psycopg2 import pool
try:
    from scraper.config import DB_CONFIG
    from scraper.state_coordinates import get_state_coordinates
except ImportError:
    from config import DB_CONFIG
    try:
        from state_coordinates import get_state_coordinates
    except ImportError:
        def get_state_coordinates(state_name):
            return None

class DatabaseManager:
    _instance = None
    _pool = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DatabaseManager, cls).__new__(cls)
            try:
                cls._pool = pool.ThreadedConnectionPool(
                    5, 50, **DB_CONFIG
                )
            except Exception as e:
                print(f"Error creating connection pool: {e}")
        return cls._instance

    def get_connection(self):
        for attempt in range(5):
            try:
                return self._pool.getconn()
            except pool.PoolError:
                if attempt < 4:
                    time.sleep(0.5 * (attempt + 1))
                else:
                    raise

    def put_connection(self, conn):
        self._pool.putconn(conn)

    def execute_query(self, query, params=None, fetch=False):
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(query, params)
                if fetch == "one" or fetch is True:
                    res = cur.fetchone()
                    conn.commit()
                    return res
                elif fetch == "all":
                    res = cur.fetchall()
                    conn.commit()
                    return res
            conn.commit()
        except Exception as e:
            conn.rollback()
            print(f"Database error: {e}")
            raise e
        finally:
            self.put_connection(conn)

    def upsert_disease(self, disease_data):
        columns = list(disease_data.keys())
        values = [disease_data[col] for col in columns]
        
        update_clauses = []
        for col in columns:
            if col == 'name': continue
            if col == 'source_urls':
                # Correctly merge arrays and remove duplicates
                update_clauses.append("source_urls = ARRAY(SELECT DISTINCT unnest(diseases.source_urls || EXCLUDED.source_urls))")
            elif col == 'mortality_rate':
                # Numeric column: only update if new value is not null
                update_clauses.append(f"mortality_rate = COALESCE(EXCLUDED.mortality_rate, diseases.mortality_rate)")
            elif col in ['category', 'description', 'symptoms', 'transmission_method', 'incubation_period', 'risk_factors']:
                # String columns: only update if not null and not empty
                update_clauses.append(f"{col} = COALESCE(NULLIF(EXCLUDED.{col}, ''), diseases.{col})")
            else:
                update_clauses.append(f"{col} = EXCLUDED.{col}")

        insert_query = f"""
            INSERT INTO diseases ({', '.join(columns)})
            VALUES ({', '.join(['%s'] * len(columns))})
            ON CONFLICT (name) DO UPDATE SET
            {', '.join(update_clauses)}
            RETURNING id;
        """
        res = self.execute_query(insert_query, values, fetch=True)
        return res[0] if res else None

    def upsert_guideline(self, guideline_data):
        columns = list(guideline_data.keys())
        values = [guideline_data[col] for col in columns]
        
        insert_query = f"""
            INSERT INTO disease_guidelines ({', '.join(columns)})
            VALUES ({', '.join(['%s'] * len(columns))})
            ON CONFLICT (disease_id, guideline_type, title) DO UPDATE SET
            {', '.join([f"{col} = EXCLUDED.{col}" for col in columns if col not in ['disease_id', 'guideline_type', 'title']])}
            RETURNING id;
        """
        res = self.execute_query(insert_query, values, fetch=True)
        return res[0] if res else None

    def upsert_outbreak(self, outbreak_data):
        columns = list(outbreak_data.keys())
        values = [outbreak_data[col] for col in columns]
        
        insert_query = f"""
            INSERT INTO outbreaks ({', '.join(columns)})
            VALUES ({', '.join(['%s'] * len(columns))})
            ON CONFLICT (disease_id, state, district, reported_date) DO UPDATE SET
            {', '.join([f"{col} = EXCLUDED.{col}" for col in columns if col not in ['disease_id', 'state', 'district', 'reported_date']])}
            RETURNING id;
        """
        res = self.execute_query(insert_query, values, fetch=True)
        return res[0] if res else None

    def upsert_trend(self, trend_data):
        columns = list(trend_data.keys())
        values = [trend_data[col] for col in columns]
        
        insert_query = f"""
            INSERT INTO trends ({', '.join(columns)})
            VALUES ({', '.join(['%s'] * len(columns))})
            ON CONFLICT (disease_id, state, district, period_type, period_start) DO UPDATE SET
            {', '.join([f"{col} = EXCLUDED.{col}" for col in columns if col not in ['disease_id', 'state', 'district', 'period_type', 'period_start']])}
            RETURNING id;
        """
        res = self.execute_query(insert_query, values, fetch=True)
        return res[0] if res else None

    def upsert_education_resource(self, resource_data):
        data = resource_data.copy()
        if 'description' in data and 'excerpt' not in data:
            data['excerpt'] = data.pop('description')
        if 'content' in data and 'summary' not in data:
            data['summary'] = data.pop('content')
        if 'source_url' in data and 'url' not in data:
            data['url'] = data.pop('source_url')

        columns = list(data.keys())
        values = [data[col] for col in columns]
        
        insert_query = f"""
            INSERT INTO education_resources ({', '.join(columns)})
            VALUES ({', '.join(['%s'] * len(columns))})
            ON CONFLICT (url) DO UPDATE SET
            {', '.join([f"{col} = EXCLUDED.{col}" for col in columns if col != 'url'])}
            RETURNING id;
        """
        res = self.execute_query(insert_query, values, fetch=True)
        return res[0] if res else None

    def log_scraper_run(self, log_data):
        columns = list(log_data.keys())
        values = [log_data[col] for col in columns]
        
        insert_query = f"""
            INSERT INTO scraper_logs ({', '.join(columns)})
            VALUES ({', '.join(['%s'] * len(columns))})
            RETURNING id;
        """
        res = self.execute_query(insert_query, values, fetch=True)
        return res[0] if res else None

    def get_disease_id_by_name(self, name):
        query = "SELECT id FROM diseases WHERE name = %s OR %s = ANY(common_names)"
        res = self.execute_query(query, (name, name), fetch=True)
        return res[0] if res else None

    def is_url_scraped(self, url, table="source_urls"):
        # Check if URL exists in any of the relevant tables
        if table == "source_urls":
            query = "SELECT id FROM diseases WHERE %s = ANY(source_urls)"
        elif table == "disease_guidelines":
            query = "SELECT id FROM disease_guidelines WHERE source_url = %s"
        elif table == "outbreaks":
            query = "SELECT id FROM outbreaks WHERE source_url = %s"
        else:
            return False
        
        res = self.execute_query(query, (url,), fetch=True)
        return res is not None

    def insert_user_report(self, report_data):
        columns = list(report_data.keys())
        values = [report_data[col] for col in columns]
        
        insert_query = f"""
            INSERT INTO user_reports ({', '.join(columns)})
            VALUES ({', '.join(['%s'] * len(columns))})
            RETURNING id;
        """
        res = self.execute_query(insert_query, values, fetch=True)
        return res[0] if res else None

    def get_education_resources(self, filter_type=None, limit=50):
        query = "SELECT id, title, resource_type, url, embed_url, thumbnail_url, duration, disease_tags, content_tags, excerpt, summary FROM education_resources"
        params = []
        
        if filter_type and filter_type != 'all':
            query += " WHERE resource_type = %s"
            params.append(filter_type)
            
        query += " ORDER BY created_at DESC LIMIT %s"
        params.append(limit)
        
        res = self.execute_query(query, params, fetch="all")
        
        resources = []
        if res:
            for r in res:
                resources.append({
                    "id": r[0],
                    "title": r[1],
                    "type": r[2],
                    "url": r[3],
                    "embedUrl": r[4],
                    "thumb": r[5],
                    "duration": r[6],
                    "disease_tags": r[7],
                    "tags": r[8],
                    "excerpt": r[9],
                    "summary": r[10]
                })
        return resources

    def get_active_outbreaks(self, disease_id=None):
        # Fetch outbreaks joined with disease info
        query = """
            SELECT o.id, d.id as disease_id, d.name, o.state, o.district, o.cases_reported, o.reported_date, o.latitude, o.longitude
            FROM outbreaks o
            JOIN diseases d ON o.disease_id = d.id
            WHERE o.status = 'active' OR o.status IS NULL
        """
        params = []
        if disease_id:
            query += " AND o.disease_id = %s"
            params.append(disease_id)
        query += " ORDER BY o.reported_date DESC LIMIT 200"
        
        res = self.execute_query(query, params if params else None, fetch="all")
        
        outbreaks = []
        if res:
            for r in res:
                # Convert Decimals to float if they exist
                lat = float(r[7]) if r[7] is not None else None
                lon = float(r[8]) if r[8] is not None else None
                state = r[3]  # state name
                
                # If coordinates are invalid (0,0 or None), try to geocode from state name
                if (lat is None or lon is None or lat == 0.0 or lon == 0.0) and state:
                    try:
                        coords = get_state_coordinates(state)
                        if coords and coords.get("lat") and coords.get("lon"):
                            lat = coords["lat"]
                            lon = coords["lon"]
                            print(f"[GEOCODE] {state} -> {lat}, {lon}")
                        else:
                            print(f"[GEOCODE] No coordinates found for state: {state}")
                    except Exception as e:
                        print(f"[GEOCODE ERROR] {state}: {e}")
                
                # Only include if we have valid coordinates
                if lat is not None and lon is not None and lat != 0.0 and lon != 0.0:
                    outbreaks.append({
                        "id": r[0],
                        "disease_id": r[1],
                        "disease": r[2],
                        "region": f"{r[4]}, {r[3]}" if r[4] else r[3],
                        "cases": r[5] or 0,
                        "date": r[6].isoformat() if r[6] else None,
                        "center": {"lat": float(lat), "lon": float(lon)}
                    })
                else:
                    print(f"[SKIP] Outbreak {r[0]} ({r[2]} in {state}) - invalid coordinates: {lat}, {lon}")
        print(f"[OUTBREAKS] Returning {len(outbreaks)} outbreaks with valid coordinates")
        return outbreaks

    def get_health_trends(self, disease_id=None):
        # Fetch trends for chart with growth_rate
        query = """
            SELECT t.id, d.id as disease_id, d.name, t.state, t.period_start, t.cases_count, t.growth_rate
            FROM trends t
            JOIN diseases d ON t.disease_id = d.id
            WHERE t.period_start >= NOW() - INTERVAL '2 years'
        """
        params = []
        if disease_id:
            query += " AND t.disease_id = %s"
            params.append(disease_id)
        query += " ORDER BY t.period_start ASC"
        
        res = self.execute_query(query, params if params else None, fetch="all")
        
        trends = []
        if res:
            for r in res:
                trends.append({
                    "id": r[0],
                    "disease_id": r[1],
                    "disease": r[2],
                    "state": r[3],
                    "date": r[4].isoformat() if r[4] else None,
                    "cases": r[5] or 0,
                    "growth_rate": float(r[6]) if r[6] is not None else None
                })
        return trends

    def get_recent_bulletins(self, limit=5, disease_id=None):
        # Fetch recent bulletins - use high severity outbreaks or recent significant ones
        query = """
            SELECT DISTINCT ON (d.name) 
                o.id, d.name, o.state, o.cases_reported, o.reported_date, o.source, o.severity, o.source_url
            FROM outbreaks o
            JOIN diseases d ON o.disease_id = d.id
            WHERE (o.severity IN ('severe', 'critical') OR o.cases_reported > 50)
        """
        params = []
        
        if disease_id:
            query += " AND o.disease_id = %s"
            params.append(disease_id)
            
        query += """
            ORDER BY d.name, o.reported_date DESC
            LIMIT %s
        """
        params.append(limit)
        
        res = self.execute_query(query, tuple(params), fetch="all")
        
        bulletins = []
        if res:
            for r in res:
                bulletins.append({
                    "title": f"{r[1]} Alert in {r[2]}",
                    "summary": f"Reported {r[3]} cases in {r[2]}. Severity: {r[6] or 'moderate'}",
                    "date": r[4].isoformat() if r[4] else None,
                    "source": r[5] or "Health Department",
                    "url": r[7]
                })
        return bulletins

    def get_diseases_with_data(self):
        """Get list of diseases that have outbreaks or trends data"""
        query = """
            SELECT DISTINCT d.id, d.name
            FROM diseases d
            WHERE EXISTS (
                SELECT 1 FROM outbreaks o WHERE o.disease_id = d.id
            ) OR EXISTS (
                SELECT 1 FROM trends t WHERE t.disease_id = d.id
            )
            ORDER BY d.name ASC
        """
        res = self.execute_query(query, fetch="all")
        
        diseases = []
        if res:
            for r in res:
                diseases.append({
                    "id": r[0],
                    "name": r[1]
                })
        return diseases

    def get_cached_places(self, amenity_type, lat, lon, radius_meters=5000):
        # Determine table name
        table_map = {
            "doctors": "connect_cache_doctors",
            "hospitals": "connect_cache_hospitals",
            "pharmacies": "connect_cache_pharmacies"
        }
        table = table_map.get(amenity_type)
        if not table:
            return []

        # Haversine distance in SQL
        # 6371 * acos(cos(radians(lat)) * cos(radians(latitude)) * cos(radians(longitude) - radians(lon)) + sin(radians(lat)) * sin(radians(latitude)))
        # Simplified: Use bounding box first for speed, then precise calc, or just precise if dataset small. 
        # Given cache size is small per user area, straight calc is fine.
        # But for SQL, let's just get everything valid and expired > NOW()
        
        query = f"""
            SELECT osm_id, name, amenity_type, speciality, latitude, longitude, phone, email, website, address, opening_hours,
                   (6371000 * acos(least(1.0, greatest(-1.0, 
                       cos(radians(%s)) * cos(radians(latitude)) * cos(radians(longitude) - radians(%s)) + 
                       sin(radians(%s)) * sin(radians(latitude))
                   )))) as distance
            FROM {table}
            WHERE expires_at > NOW()
            AND (6371000 * acos(least(1.0, greatest(-1.0, 
                       cos(radians(%s)) * cos(radians(latitude)) * cos(radians(longitude) - radians(%s)) + 
                       sin(radians(%s)) * sin(radians(latitude))
                   )))) <= %s
            ORDER BY distance ASC
            LIMIT 50
        """
        # Params repeated for distance calcs: lat, lon, lat; lat, lon, lat, radius
        params = (lat, lon, lat, lat, lon, lat, radius_meters)
        
        res = self.execute_query(query, params, fetch="all")
        places = []
        if res:
            for r in res:
                places.append({
                    "osm_id": r[0],
                    "name": r[1],
                    "amenity_type": r[2],
                    "speciality": r[3],
                    "latitude": float(r[4]),
                    "longitude": float(r[5]),
                    "phone": r[6],
                    "email": r[7],
                    "website": r[8],
                    "address": r[9],
                    "opening_hours": r[10],
                    "distance": float(r[11]),
                    "source": "Cache"
                })
        return places

    def upsert_cached_places(self, amenity_type, data):
        table_map = {
            "doctors": "connect_cache_doctors",
            "hospitals": "connect_cache_hospitals",
            "pharmacies": "connect_cache_pharmacies"
        }
        table = table_map.get(amenity_type)
        if not table:
            return

        # Prepare values
        # (osm_id, name, amenity_type, speciality, latitude, longitude, phone, email, website, address, opening_hours, expires_at)
        values = []
        for item in data:
            values.append((
                item["osm_id"],
                item["name"],
                item["amenity_type"],
                item.get("speciality"),
                item["latitude"],
                item["longitude"],
                item.get("phone"),
                item.get("email"),
                item.get("website"),
                item.get("address"),
                item.get("opening_hours"),
                # date + 7 days
                # In python just pass string, adapter handles it, or datetime object
            ))
        
        # We need to construct the Execute Values query manually or loop.
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                query = f"""
                    INSERT INTO {table} (osm_id, name, amenity_type, speciality, latitude, longitude, phone, email, website, address, opening_hours, expires_at)
                    VALUES %s
                    ON CONFLICT (osm_id) DO UPDATE SET
                    name = EXCLUDED.name,
                    phone = EXCLUDED.phone,
                    address = EXCLUDED.address,
                    expires_at = NOW() + INTERVAL '7 days'
                """
                # Handle expires_at in SQL or Pass it.
                # Let's clean up values to not have python logic in SQL string too much
                # Actually execute_values is best
                
                # Transform values to match %s
                clean_values = []
                for v in values:
                    # Append 7 days expiry logic is easier in SQL if we don't pass it, but execute_values expects matching length
                    # Let's pass 'NOW() + ...' as a string? No, psycopg2 will quote it.
                    # Best to pass datetime in python.
                    from datetime import datetime, timedelta
                    expires = datetime.now() + timedelta(days=7)
                    clean_values.append(v + (expires,))

                execute_values(cur, query, clean_values)
                conn.commit()
        except Exception as e:
            conn.rollback()
            print(f"Error upserting cache: {e}")
        finally:
            self.put_connection(conn)

    def log_emergency(self, usage_type, condition, lat, lon, hospital_name, hospital_dist):
        query = """
            INSERT INTO emergency_logs (emergency_type, condition_described, latitude, longitude, nearest_hospital_name, nearest_hospital_distance_m)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
        """
        res = self.execute_query(query, (usage_type, condition, lat, lon, hospital_name, hospital_dist), fetch=True)
        return res[0] if res else None

    def check_emergency_cluster(self, lat, lon, condition_text):
        # Check for similar conditions within 5km in last 7 days
        # Simple text similarity or just count logs in radius
        # For now, just count logs in 5km radius regardless of condition text exact match (or use ILIKE)
        
        query = """
            SELECT count(*)
            FROM emergency_logs
            WHERE created_at > NOW() - INTERVAL '7 days'
            AND (6371000 * acos(least(1.0, greatest(-1.0, 
                       cos(radians(%s)) * cos(radians(latitude)) * cos(radians(longitude) - radians(%s)) + 
                       sin(radians(%s)) * sin(radians(latitude))
                   )))) <= 5000
            AND condition_described ILIKE %s
        """
        # condition match loose: %word%
        # assume condition_text is "fever" -> %fever%
        # If text is long, maybe take first word? For now, exact containment.
        search_term = f"%{condition_text.split()[0] if condition_text else ''}%" 
        
        res = self.execute_query(query, (lat, lon, lat, search_term), fetch=True)
        return res[0] if res else 0

    def get_first_aid(self, condition_text):
        # condition_text like "snake bite", "burns", "heart attack"
        # query disease_guidelines where guideline_type='first_aid' and title ILIKE condition
        query = """
            SELECT title, content, steps, source
            FROM disease_guidelines
            WHERE guideline_type = 'first_aid'
            AND (title ILIKE %s OR %s ILIKE ANY(string_to_array(title, ' '))) 
        """
        # Try exact phrase match first
        term = f"%{condition_text}%"
        res = self.execute_query(query, (term, condition_text), fetch=True)
        
        if not res and len(condition_text.split()) > 1:
            # Try matching any word if phrase failed
            # But "bite" might match "dog bite" for "snake bite" - risky.
            # Let's stick to phrase match or partial.
            pass
            
        if res:
             return {
                 "title": res[0],
                 "content": res[1],
                 "steps": res[2], # jsonb
                 "source": res[3]
             }
        return None

    def create_chat_session(self, title=None):
        query = """
            INSERT INTO chat_sessions (title)
            VALUES (%s)
            RETURNING id
        """
        res = self.execute_query(query, (title,), fetch="one")
        return str(res[0]) if res else None

    def get_chat_sessions(self, limit=5):
        query = """
            SELECT id, title, created_at 
            FROM chat_sessions 
            WHERE id::text ~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
            ORDER BY created_at DESC 
            LIMIT %s
        """
        res = self.execute_query(query, (limit,), fetch="all")
        sessions = []
        if res:
            for r in res:
                sessions.append({
                    "id": str(r[0]),
                    "title": r[1] or "New Chat",
                    "created_at": r[2].isoformat() if r[2] else None
                })
        return sessions

    def get_chat_messages(self, session_id):
        query = """
            SELECT role, content, created_at 
            FROM chat_history 
            WHERE session_id = %s 
            ORDER BY created_at ASC
        """
        res = self.execute_query(query, (session_id,), fetch="all")
        messages = []
        if res:
            for r in res:
                messages.append({
                    "role": r[0],
                    "content": r[1],
                    "timestamp": r[2].isoformat() if r[2] else None
                })
        return messages

    def add_chat_message(self, session_id, role, content, language='en'):
        query = """
            INSERT INTO chat_history (session_id, role, content, language)
            VALUES (%s, %s, %s, %s)
        """
        self.execute_query(query, (session_id, role, content, language))

    def update_session_title(self, session_id, title):
        query = "UPDATE chat_sessions SET title = %s WHERE id = %s"
        self.execute_query(query, (title, session_id))

    def log_knowledge_gap(self, gap_type, query_text, related_disease, location, lat=None, lon=None, occurrence_count=1):
        query = """
            INSERT INTO knowledge_gaps (gap_type, query_text, related_disease, location, latitude, longitude, occurrence_count)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO NOTHING -- Should normally be serial insert, but just in case unique constraints added later
            RETURNING id
        """
        res = self.execute_query(query, (gap_type, query_text, related_disease, location, lat, lon, occurrence_count), fetch=True)
        return res[0] if res else None

    # ── URL Cache (Change Detection) ────────────────────────────────────────

    def get_url_cache(self, url):
        """Get cached ETag / Last-Modified for *url*. Returns dict or None."""
        query = "SELECT etag, last_modified, last_checked, last_changed FROM url_cache WHERE url = %s"
        try:
            res = self.execute_query(query, (url,), fetch=True)
            if res:
                return {
                    "etag": res[0],
                    "last_modified": res[1],
                    "last_checked": res[2],
                    "last_changed": res[3],
                }
        except Exception:
            pass  # Table may not exist yet
        return None

    def update_url_cache(self, url, etag=None, last_modified=None):
        """Upsert ETag / Last-Modified for *url*."""
        query = """
            INSERT INTO url_cache (url, etag, last_modified, last_checked, last_changed)
            VALUES (%s, %s, %s, NOW(), NOW())
            ON CONFLICT (url) DO UPDATE SET
                etag = COALESCE(EXCLUDED.etag, url_cache.etag),
                last_modified = COALESCE(EXCLUDED.last_modified, url_cache.last_modified),
                last_checked = NOW(),
                last_changed = CASE
                    WHEN EXCLUDED.etag IS DISTINCT FROM url_cache.etag
                      OR EXCLUDED.last_modified IS DISTINCT FROM url_cache.last_modified
                    THEN NOW()
                    ELSE url_cache.last_changed
                END
        """
        try:
            self.execute_query(query, (url, etag, last_modified))
        except Exception:
            pass  # Table may not exist yet

    # ── Cross-source content de-dup ─────────────────────────────────────────

    def is_content_fingerprint_seen(self, content_hash: str) -> bool:
        """Return True if this content hash was already ingested."""
        try:
            res = self.execute_query(
                "SELECT 1 FROM content_fingerprints WHERE content_hash = %s",
                (content_hash,),
                fetch=True,
            )
            return bool(res)
        except Exception:
            return False

    def remember_content_fingerprint(self, content_hash: str, source: str = None, sample_url: str = None) -> None:
        """Insert a content hash if missing (idempotent)."""
        try:
            self.execute_query(
                """
                INSERT INTO content_fingerprints (content_hash, source, sample_url)
                VALUES (%s, %s, %s)
                ON CONFLICT (content_hash) DO NOTHING
                """,
                (content_hash, source, sample_url),
            )
        except Exception:
            # If table isn't migrated yet, just skip de-dup
            return

    # ── Bulletin Text (LangChain context) ────────────────────────────────────

    def upsert_bulletin_text(self, data):
        """Insert raw bulletin text. ON CONFLICT (url) DO NOTHING."""
        columns = list(data.keys())
        values = [data[col] for col in columns]
        query = f"""
            INSERT INTO bulletin_texts ({', '.join(columns)})
            VALUES ({', '.join(['%s'] * len(columns))})
            ON CONFLICT (url) DO NOTHING
            RETURNING id
        """
        try:
            res = self.execute_query(query, values, fetch=True)
            return res[0] if res else None
        except Exception as e:
            print(f"Error upserting bulletin_text: {e}")
            return None

    # ── Enhanced Upserts with GREATEST ───────────────────────────────────────

    def upsert_outbreak_greatest(self, outbreak_data):
        """
        Upsert outbreak using GREATEST for case/death counts.
        Later reports are always more complete, so we keep the max.
        """
        columns = list(outbreak_data.keys())
        values = [outbreak_data[col] for col in columns]

        update_clauses = []
        for col in columns:
            if col in ('disease_id', 'state', 'district', 'reported_date'):
                continue
            if col == 'cases_reported':
                update_clauses.append("cases_reported = GREATEST(outbreaks.cases_reported, EXCLUDED.cases_reported)")
            elif col == 'deaths_reported':
                update_clauses.append("deaths_reported = GREATEST(outbreaks.deaths_reported, EXCLUDED.deaths_reported)")
            else:
                update_clauses.append(f"{col} = EXCLUDED.{col}")

        query = f"""
            INSERT INTO outbreaks ({', '.join(columns)})
            VALUES ({', '.join(['%s'] * len(columns))})
            ON CONFLICT (disease_id, state, district, reported_date) DO UPDATE SET
            {', '.join(update_clauses)}
            RETURNING id
        """
        res = self.execute_query(query, values, fetch=True)
        return res[0] if res else None

    def upsert_trend_greatest(self, trend_data):
        """
        Upsert trend using GREATEST for cases_count.
        """
        columns = list(trend_data.keys())

        # Auto-calculate period_end if missing
        if 'period_end' not in columns and 'period_start' in trend_data and 'period_type' in trend_data:
            from datetime import timedelta
            start = trend_data['period_start']
            p_type = trend_data['period_type']
            if p_type == 'weekly':
                trend_data['period_end'] = start + timedelta(days=6)
            elif p_type == 'monthly':
                # approximate
                trend_data['period_end'] = start + timedelta(days=29)
            elif p_type == 'annual':
                trend_data['period_end'] = start
            elif p_type == 'daily':
                trend_data['period_end'] = start
            else:
                trend_data['period_end'] = start
            columns.append('period_end')

        values = [trend_data[col] for col in columns]

        update_clauses = []
        for col in columns:
            if col in ('disease_id', 'state', 'district', 'period_type', 'period_start'):
                continue
            if col == 'cases_count':
                update_clauses.append("cases_count = GREATEST(trends.cases_count, EXCLUDED.cases_count)")
            else:
                update_clauses.append(f"{col} = EXCLUDED.{col}")

        query = f"""
            INSERT INTO trends ({', '.join(columns)})
            VALUES ({', '.join(['%s'] * len(columns))})
            ON CONFLICT (disease_id, state, district, period_type, period_start) DO UPDATE SET
            {', '.join(update_clauses)}
            RETURNING id
        """
        res = self.execute_query(query, values, fetch=True)
        return res[0] if res else None

    # ── Medicines ───────────────────────────────────────────────────────────

    def upsert_medicine(self, medicine_data):
        """
        Upsert medicine handling both medicine_names (generic) and medicines (specifics).
        Expects: generic_name, brand_name, manufacturer, dosage_form, etc.
        """
        generic_name = medicine_data.get('generic_name')
        if not generic_name:
            return None

        # 1. Upsert medicine_names
        name_query = """
            INSERT INTO medicine_names (name)
            VALUES (%s)
            ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name
            RETURNING id
        """
        res = self.execute_query(name_query, (generic_name,), fetch=True)
        generic_id = res[0] if res else None

        if not generic_id:
            # Fallback if returning didn't work (e.g., exact conflict without update)
            res = self.execute_query("SELECT id FROM medicine_names WHERE name = %s", (generic_name,), fetch=True)
            generic_id = res[0] if res else None
            if not generic_id:
                return None

        # 2. Upsert medicines (if we have formulation info)
        brand = medicine_data.get('brand_name') or 'Generic'
        dosage = medicine_data.get('dosage_form') or 'Unknown'
        strength = medicine_data.get('strength') or 'Unknown'
        manuf = medicine_data.get('manufacturer')
        sched = medicine_data.get('schedule')
        src = medicine_data.get('source')
        url = medicine_data.get('source_url')

        med_query = """
            INSERT INTO medicines (generic_id, brand_name, manufacturer, dosage_form, strength, schedule, source, source_url)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (generic_id, brand_name, dosage_form, strength) DO UPDATE SET
                manufacturer = COALESCE(EXCLUDED.manufacturer, medicines.manufacturer),
                schedule = COALESCE(EXCLUDED.schedule, medicines.schedule)
            RETURNING id
        """
        res = self.execute_query(med_query, (generic_id, brand, manuf, dosage, strength, sched, src, url), fetch=True)
        return res[0] if res else None

    # ── Raw Connection (for transactional use) ───────────────────────────────

    def get_raw_connection(self):
        """Return a raw connection for manual transaction management."""
        return self.get_connection()

    # ── Schema Migration ─────────────────────────────────────────────────────

    @classmethod
    def run_schema_migration(cls):
        """
        Create new tables and add new columns required by the enhanced scraper.
        Safe to run multiple times (IF NOT EXISTS / IF NOT EXISTS).
        """
        instance = cls()
        conn = instance.get_connection()
        try:
            with conn.cursor() as cur:
                # -- bulletin_texts table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS bulletin_texts (
                        id SERIAL PRIMARY KEY,
                        source VARCHAR(100) NOT NULL,
                        disease_mentioned VARCHAR(200),
                        state_mentioned VARCHAR(100),
                        raw_text TEXT NOT NULL,
                        published_date DATE,
                        url TEXT UNIQUE,
                        week_number INTEGER,
                        scraped_at TIMESTAMPTZ DEFAULT NOW()
                    )
                """)
                cur.execute("CREATE INDEX IF NOT EXISTS idx_bulletin_disease ON bulletin_texts (disease_mentioned)")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_bulletin_date ON bulletin_texts (published_date DESC)")

                # -- url_cache table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS url_cache (
                        url TEXT PRIMARY KEY,
                        etag TEXT,
                        last_modified TEXT,
                        last_checked TIMESTAMPTZ DEFAULT NOW(),
                        last_changed TIMESTAMPTZ DEFAULT NOW()
                    )
                """)

                # -- content_fingerprints table (cross-source de-dup)
                # Stores hashes of normalized content so we don't re-ingest the same text
                # from different URLs/sources.
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS content_fingerprints (
                        content_hash TEXT PRIMARY KEY,
                        source VARCHAR(120),
                        sample_url TEXT,
                        first_seen TIMESTAMPTZ DEFAULT NOW()
                    )
                """)
                cur.execute("CREATE INDEX IF NOT EXISTS idx_content_fingerprints_source ON content_fingerprints (source)")

                # -- trends table enhancements
                cur.execute("ALTER TABLE trends ADD COLUMN IF NOT EXISTS source_confidence VARCHAR(20) DEFAULT 'medium'")
                cur.execute("ALTER TABLE trends ADD COLUMN IF NOT EXISTS data_type VARCHAR(20) DEFAULT 'cumulative'")
                cur.execute("ALTER TABLE trends ADD COLUMN IF NOT EXISTS report_week INTEGER")

                # -- medicines tables
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS medicine_names (
                        id SERIAL PRIMARY KEY,
                        name VARCHAR(300) UNIQUE NOT NULL,
                        drug_class VARCHAR(200),
                        description TEXT,
                        created_at TIMESTAMPTZ DEFAULT NOW(),
                        updated_at TIMESTAMPTZ DEFAULT NOW()
                    )
                """)
                cur.execute("""
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
                    )
                """)

                # -- scraper_logs enhancements
                cur.execute("ALTER TABLE scraper_logs ADD COLUMN IF NOT EXISTS records_failed INTEGER DEFAULT 0")
                cur.execute("ALTER TABLE scraper_logs ADD COLUMN IF NOT EXISTS pdfs_processed INTEGER DEFAULT 0")
                cur.execute("ALTER TABLE scraper_logs ADD COLUMN IF NOT EXISTS error_details TEXT")

                conn.commit()
                print("[MIGRATION] Schema migration completed successfully.")
        except Exception as e:
            conn.rollback()
            print(f"[MIGRATION ERROR] {e}")
        finally:
            instance.put_connection(conn)

    def close(self):
        if self._pool:
            self._pool.closeall()
