"""
Huvudsaklig routing-modul som koordinerar olika providers
"""

import streamlit as st
import hashlib
from typing import Tuple, Optional, List
from config import CACHE_TTL
from models import RouteInfo
from routing_providers import OpenRouteServiceProvider, GraphHopperProvider

def create_cache_key(
    coordinates: List[List[float]], 
    distance: float,
    mode: str, 
    tolerance: float, 
    seed: int = 0,
    provider: str = "auto"
) -> str:
    """Skapa cache-nyckel för routing"""
    key_str = f"{coordinates}_{distance}_{mode}_{tolerance}_{seed}_{provider}"
    return hashlib.md5(key_str.encode()).hexdigest()

@st.cache_data(ttl=CACHE_TTL)
def get_best_route(
    start: Tuple[float, float],
    end: Optional[Tuple[float, float]],
    distance_km: float,
    tolerance_percent: float,
    mode: str = "loop",
    seed: int = 0,
    provider: str = "auto",
    _cache_key: str = ""
) -> Optional[RouteInfo]:
    """
    Hämta bästa möjliga rutt från tillgängliga providers
    
    Args:
        start: (lat, lon) för startpunkt
        end: (lat, lon) för slutpunkt (endast point-to-point)
        distance_km: Önskad distans i km
        tolerance_percent: Tolerans i procent
        mode: "loop" eller "point-to-point"
        seed: Seed för variation
        provider: "auto", "ors", "graphhopper", eller "both"
        _cache_key: Cache-nyckel
    
    Returns:
        RouteInfo eller None vid fel
    """
    
    routes = []
    
    # Välj providers baserat på inställning
    if provider == "auto":
        # Använd GraphHopper om tillgänglig (bättre precision), annars ORS
        if "GRAPHHOPPER_API_KEY" in st.secrets:
            provider = "graphhopper"
        elif "ORS_API_KEY" in st.secrets:
            provider = "ors"
        else:
            st.error("Ingen API-nyckel konfigurerad!")
            return None
    
    # Hämta rutter från valda providers
    if provider in ["ors", "both"]:
        if "ORS_API_KEY" in st.secrets:
            with st.spinner("Testar OpenRouteService..."):
                ors_provider = OpenRouteServiceProvider()
                ors_route = ors_provider.get_route(
                    start, end, distance_km, tolerance_percent, mode, seed
                )
                if ors_route:
                    routes.append(ors_route)
    
    if provider in ["graphhopper", "both"]:
        if "GRAPHHOPPER_API_KEY" in st.secrets:
            with st.spinner("Testar GraphHopper..."):
                gh_provider = GraphHopperProvider()
                gh_route = gh_provider.get_route(
                    start, end, distance_km, tolerance_percent, mode, seed
                )
                if gh_route:
                    routes.append(gh_route)
    
    # Om vi har flera rutter, välj den bästa (tyst)
    if len(routes) > 1:
        target_distance = distance_km * 1000
        tolerance_m = target_distance * (tolerance_percent / 100)
        
        # Sortera rutter: först de inom tolerans, sedan närmast måldistans
        def route_score(route):
            deviation = abs(route.distance - target_distance)
            within_tolerance = deviation <= tolerance_m
            # Lägre poäng är bättre
            return (0 if within_tolerance else 1, deviation)
        
        routes.sort(key=route_score)
    
    return routes[0] if routes else None