# Indian State and District Coordinates Mapping
# Fallback coordinates for geocoding when database has 0.0, 0.0

INDIAN_STATE_COORDINATES = {
    "Andhra Pradesh": {"lat": 15.9129, "lon": 79.7400},
    "Arunachal Pradesh": {"lat": 28.2180, "lon": 94.7278},
    "Assam": {"lat": 26.2006, "lon": 92.9376},
    "Bihar": {"lat": 25.0961, "lon": 85.3131},
    "Chhattisgarh": {"lat": 21.2787, "lon": 81.8661},
    "Goa": {"lat": 15.2993, "lon": 74.1240},
    "Gujarat": {"lat": 23.0225, "lon": 72.5714},
    "Haryana": {"lat": 29.0588, "lon": 76.0856},
    "Himachal Pradesh": {"lat": 31.1048, "lon": 77.1734},
    "Jharkhand": {"lat": 23.6102, "lon": 85.2799},
    "Karnataka": {"lat": 12.9716, "lon": 77.5946},
    "Kerala": {"lat": 10.8505, "lon": 76.2711},
    "Madhya Pradesh": {"lat": 23.2599, "lon": 77.4126},
    "Maharashtra": {"lat": 19.0760, "lon": 72.8777},
    "Manipur": {"lat": 24.6637, "lon": 93.9063},
    "Meghalaya": {"lat": 25.4670, "lon": 91.3662},
    "Mizoram": {"lat": 23.1645, "lon": 92.9376},
    "Nagaland": {"lat": 26.1584, "lon": 94.5624},
    "Odisha": {"lat": 20.9517, "lon": 85.0985},
    "Punjab": {"lat": 31.1471, "lon": 75.3412},
    "Rajasthan": {"lat": 26.9124, "lon": 75.7873},
    "Sikkim": {"lat": 27.5330, "lon": 88.5122},
    "Tamil Nadu": {"lat": 13.0827, "lon": 80.2707},
    "Telangana": {"lat": 17.3850, "lon": 78.4867},
    "Tripura": {"lat": 23.9408, "lon": 91.9882},
    "Uttar Pradesh": {"lat": 26.8467, "lon": 80.9462},
    "Uttarakhand": {"lat": 30.0668, "lon": 79.0193},
    "West Bengal": {"lat": 22.5726, "lon": 88.3639},
    "Delhi": {"lat": 28.6139, "lon": 77.2090},
    "Jammu and Kashmir": {"lat": 34.0837, "lon": 74.7973},
    "Ladakh": {"lat": 34.1526, "lon": 77.5770},
    "Puducherry": {"lat": 11.9416, "lon": 79.8083},
    "Chandigarh": {"lat": 30.7333, "lon": 76.7794},
    "Andaman and Nicobar Islands": {"lat": 11.7401, "lon": 92.6586},
    "Dadra and Nagar Haveli and Daman and Diu": {"lat": 20.1809, "lon": 73.0169},
    "Lakshadweep": {"lat": 10.5667, "lon": 72.6417}
}

def get_state_coordinates(state_name):
    """Get coordinates for an Indian state"""
    if not state_name:
        return None
    
    # Try exact match first
    if state_name in INDIAN_STATE_COORDINATES:
        return INDIAN_STATE_COORDINATES[state_name]
    
    # Try case-insensitive match
    for state, coords in INDIAN_STATE_COORDINATES.items():
        if state.lower() == state_name.lower():
            return coords
    
    # Try partial match
    state_lower = state_name.lower()
    for state, coords in INDIAN_STATE_COORDINATES.items():
        if state.lower() in state_lower or state_lower in state.lower():
            return coords
    
    return None
