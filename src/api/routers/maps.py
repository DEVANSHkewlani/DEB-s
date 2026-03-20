from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import sys
import os
import requests
import json
import math
from datetime import datetime, timedelta
import time
import random

# Add parent directory to path to import scraper.db
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from scraper.db import DatabaseManager

router = APIRouter()

# Constants
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
MAX_RETRIES = 3
Base_BACKOFF_SECONDS = 2

def get_distance_meters(lat1, lon1, lat2, lon2):
    """
    Calculate Haversine distance between two points in meters.
    """
    R = 6371000  # Radius of Earth in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi / 2)**2 + \
        math.cos(phi1) * math.cos(phi2) * \
        math.sin(delta_lambda / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c

class EmergencyRequest(BaseModel):
    latitude: float
    longitude: float
    condition_text: str
    radius: Optional[int] = 5000 # Default 5km

@router.get("/nearby")
async def get_nearby(
    lat: float, 
    lon: float, 
    radius: int = 5000, 
    type_filter: str = "all"
):
    """
    Find nearby doctors, hospitals, and pharmacies.
    Uses caching (7 days) and falls back to Overpass API.
    """
    # Clamp radius to keep Overpass reliable and prevent accidental huge queries.
    # UI supplies meters; we allow 250m–50km.
    try:
        radius = int(radius)
    except Exception:
        radius = 5000
    radius = max(250, min(radius, 50000))
    requested_radius = radius
    # If the radius is very small, Overpass may legitimately return 0 because few amenities exist
    # in that exact circle. To avoid "radius feels broken", we fetch at least 5km to warm the cache,
    # then filter results down to the requested radius for the response.
    fetch_radius = max(requested_radius, 5000)

    db = DatabaseManager()
    
    amenity_types = []
    if type_filter == "all":
        amenity_types = ["doctors", "hospitals", "pharmacies"]
    elif type_filter == "doctors":
        amenity_types = ["doctors"]
    elif type_filter == "hospitals":
        amenity_types = ["hospitals"]
    elif type_filter == "pharmacies":
        amenity_types = ["pharmacies"]
    else:
        # Fallback/Default
        amenity_types = ["doctors", "hospitals", "pharmacies"]

    results = []

    for amenity in amenity_types:
        # 1. Check Cache
        cached_data = db.get_cached_places(amenity, lat, lon, requested_radius)
        
        # We need a strategy to decide if we need to fetch fresh data.
        # Simple strategy: If cache returns 0 results for this type in this radius, fetch fresh.
        # Or check if any result is "stale" (handled by DB query typically, but here we just check for existence).
        # A robust way: check connect_cache_X table for *any* non-expired entries in the bounding box? 
        # For simplicity in this implementation: 
        # If we find < 5 results in cache, we assume might be incomplete/empty and try fetching fresh once.
        # (Optimally we'd have a 'search_log' to know if we searched here recently, but cache keys work too)
        
        if len(cached_data) < 5:
            print(f"Cache miss or low count ({len(cached_data)}) for {amenity} at {lat}, {lon}. Fetching from OSM...")
            try:
                osm_data = fetch_from_overpass(amenity, lat, lon, fetch_radius)
                if osm_data:
                    # Save to db
                    db.upsert_cached_places(amenity, osm_data)
                    # Merge fresh data (deduplication happens in DB or here)
                    # For response, we can just use the osm_data converted to format + existing cached if any
                    # But simpler to just re-query cache or assume osm_data is the source of truth now.
                    # Let's re-query cache to get consistent IDs and formats if we trust DB upsert
                    # Or just format osm_data for return
                    # Return only what fits the requested radius (even if we fetched wider)
                    results.extend([r for r in osm_data if r.get("distance") is not None and r["distance"] <= requested_radius])
                    # Be nice to the API
                    time.sleep(1) 
                    continue 
            except Exception as e:
                print(f"Overpass fetch error for {amenity}: {e}")
        
        # If we didn't fetch fresh (or failed), use cached
        if cached_data:
            # Add distance to results
            for item in cached_data:
                item['distance'] = get_distance_meters(lat, lon, item['latitude'], item['longitude'])
            results.extend(cached_data)

    # Sort by distance
    results.sort(key=lambda x: x.get('distance', float('inf')))
    
    return results

def fetch_from_overpass(amenity_type, lat, lon, radius):
    """
    Fetch nodes from Overpass API.
    """
    # Construct Overpass QL query
    timeout = 25
    osm_amenity = amenity_type.rstrip('s')  # hospitals->hospital, pharmacies->pharmacy

    if amenity_type == "doctors":
        query = (
            f"[out:json][timeout:{timeout}];("
            f"node['amenity'='doctors'](around:{radius},{lat},{lon});"
            f"node['amenity'='clinic'](around:{radius},{lat},{lon});"
            f"way['amenity'='doctors'](around:{radius},{lat},{lon});"
            f"way['amenity'='clinic'](around:{radius},{lat},{lon});"
            f"relation['amenity'='doctors'](around:{radius},{lat},{lon});"
            f"relation['amenity'='clinic'](around:{radius},{lat},{lon});"
            f");out center qt;"
        )
    else:
        query = (
            f"[out:json][timeout:{timeout}];("
            f"node['amenity'='{osm_amenity}'](around:{radius},{lat},{lon});"
            f"way['amenity'='{osm_amenity}'](around:{radius},{lat},{lon});"
            f"relation['amenity'='{osm_amenity}'](around:{radius},{lat},{lon});"
            f");out center qt;"
        )

    # Implement retry mechanism
    for attempt in range(MAX_RETRIES):
        try:
            response = requests.get(OVERPASS_URL, params={'data': query}, timeout=30)
            
            if response.status_code == 429 or response.status_code == 504:
                # API busy, wait and retry
                wait_time = Base_BACKOFF_SECONDS * (2 ** attempt) + random.uniform(0, 1)
                print(f"Overpass API busy (Status {response.status_code}). Retrying in {wait_time:.1f}s...")
                time.sleep(wait_time)
                continue
                
            if response.status_code == 200:
                # Check for "busy" text in response body which sometimes happens with 200 OK
                if "The server is busy at the moment" in response.text:
                    wait_time = Base_BACKOFF_SECONDS * (2 ** attempt) + random.uniform(0, 1)
                    print(f"Overpass API reported busy in body. Retrying in {wait_time:.1f}s...")
                    time.sleep(wait_time)
                    continue
                    
                break # Success!
            
            # Other errors, just print and maybe retry or break? 
            # 400 is bad request, don't retry. 5xx might be retriable but let's stick to busy signals for now.
            print(f"Overpass API returned status {response.status_code}")
            
        except requests.exceptions.RequestException as e:
            print(f"Overpass request failed: {e}")
            wait_time = Base_BACKOFF_SECONDS * (2 ** attempt) + random.uniform(0, 1)
            time.sleep(wait_time)

    # After loop, check if we have a valid response
    if 'response' in locals() and response.status_code == 200:
        data = response.json()
        parsed_results = []
        for element in data.get('elements', []):
            if 'tags' in element and ('lat' in element or 'center' in element):
                # Basic parsing
                name = element['tags'].get('name', 'Unknown')
                
                # Try to get lat/lon (nodes have it, ways need center but 'out body' might not give center for ways unless 'center' specified)
                # For simplicity, we stick to nodes mostly or check for lat/lon keys.
                # 'out body' on ways returns nodes refs, not coords unless recurse.
                # To keep it simple for this implementation plan level: use whatever has lat/lon
                
                item_lat = element.get('lat')
                item_lon = element.get('lon')
                if (item_lat is None or item_lon is None) and isinstance(element.get("center"), dict):
                    item_lat = element["center"].get("lat")
                    item_lon = element["center"].get("lon")
                
                if item_lat is not None and item_lon is not None:
                    parsed_results.append({
                        "osm_id": element['id'],
                        "name": name,
                        "amenity_type": amenity_type,
                        "speciality": element['tags'].get('healthcare:speciality', element['tags'].get('speciality', None)),
                        "latitude": item_lat,
                        "longitude": item_lon,
                        "phone": element['tags'].get('phone', element['tags'].get('contact:phone', None)),
                        "email": element['tags'].get('email', None),
                        "website": element['tags'].get('website', None),
                        "address": f"{element['tags'].get('addr:street', '')} {element['tags'].get('addr:city', '')}".strip(),
                        "opening_hours": element['tags'].get('opening_hours', None),
                        "distance": get_distance_meters(lat, lon, item_lat, item_lon),
                        "source": "OSM"
                    })
        return parsed_results
    else:
        print(f"Overpass API Error: {response.status_code}")
        return []

@router.post("/emergency")
async def emergency_assist(request: EmergencyRequest):
    """
    Handle emergency requests: log, check clusters, find hospital, provide first aid.
    """
    db = DatabaseManager()
    
    # 1. Log the emergency
    # Since we can't easily modify EmergencyRequest to include severity for now without changing frontend usage,
    # we'll infer or set default.
    
    # 2. Check for Clusters (Knowledge Gap)
    # This logic belongs in DB manager usually or here.
    # Check for > 20 logs in last 7 days within 5km
    cluster_count = db.check_emergency_cluster(request.latitude, request.longitude, request.condition_text)
    if cluster_count >= 20:
        # Log Knowledge Gap
        db.log_knowledge_gap(
            gap_type="emergency_cluster",
            query_text=f"High frequency of emergency: {request.condition_text}",
            related_disease=request.condition_text, # Heuristic
            location=f"Lat: {request.latitude}, Lon: {request.longitude}",
            lat=request.latitude,
            lon=request.longitude,
            occurrence_count=cluster_count
        )
        print(f"Emergency Cluster Detected! {cluster_count} incidents.")

    # 3. Find Nearest Hospital
    nearest_hospital = None
    try:
        # Use existing helper logic
        hospitals = await get_nearby(request.latitude, request.longitude, request.radius, "hospitals")
        nearest_hospital = hospitals[0] if hospitals else None
        
        # If no hospital in radius, try expanding radius once to 10km (if user radius < 10000)
        if not nearest_hospital and request.radius < 10000:
             hospitals = await get_nearby(request.latitude, request.longitude, 10000, "hospitals")
             nearest_hospital = hospitals[0] if hospitals else None
             
        # Log emergency only if we successfully tried finding a hospital (or just log regardless?)
        log_id = db.log_emergency(
            usage_type="ambulance", # generic for now
            condition=request.condition_text,
            lat=request.latitude,
            lon=request.longitude,
            hospital_name=nearest_hospital['name'] if nearest_hospital else None,
            hospital_dist=nearest_hospital['distance'] if nearest_hospital else None
        )
    except Exception as e:
        print(f"Error finding hospital during emergency: {e}")
        # Proceed to First Aid even if hospital search fails

    # 4. Find First Aid
    # Search guidelines for "first_aid" type and simple text match
    first_aid_content = None
    first_aid_guideline = db.get_first_aid(request.condition_text)
    
    if first_aid_guideline:
        first_aid_content = first_aid_guideline
    else:
        # Knowledge Gap
        db.log_knowledge_gap(
            gap_type="missing_first_aid",
            query_text=request.condition_text,
            related_disease="unknown_emergency",
            location=None
        )
        first_aid_content = {
            "title": "General Emergency Advice", 
            "content": "Keep calm. Call emergency services immediately. Ensure the patient is breathing and in a safe position. Do not move the patient unless there is immediate danger.",
            "steps": [
                "Ensure the scene is safe for you and the patient.",
                "Check for response: Alertness, Breathing.",
                "Call 108 or 112 immediately.",
                "If not breathing, start CPR if trained.",
                "Control any severe bleeding with pressure."
            ]
        }

    return {
        "hospital": nearest_hospital,
        "first_aid": first_aid_content,
        "is_knowledge_gap": first_aid_guideline is None
    }
