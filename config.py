"""
Konfiguration och konstanter för löparruttplaneraren
"""

# Standardvärden
DEFAULT_DISTANCE = 5.0
DEFAULT_TOLERANCE = 5.0
DEFAULT_PACE = "5:30"
DEFAULT_CENTER = [59.3293, 18.0686]  # Stockholm

# API URLs
ORS_BASE_URL = "https://api.openrouteservice.org"
GRAPHHOPPER_BASE_URL = "https://graphhopper.com/api/1"
NOMINATIM_BASE_URL = "https://nominatim.openstreetmap.org"
MAPBOX_BASE_URL = "https://api.mapbox.com/geocoding/v6"

# Routing-inställningar
MAX_ROUTE_ATTEMPTS = 10
PERFECT_TOLERANCE_PERCENT = 1.0  # Sluta söka om vi hittar rutt inom 1%

# Cache-inställningar
CACHE_TTL = 3600  # 1 timme