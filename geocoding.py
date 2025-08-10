"""
Geokodningsfunktioner för att konvertera mellan adresser och koordinater
"""

import streamlit as st
import requests
import time
from typing import Optional, Tuple
from config import NOMINATIM_BASE_URL, MAPBOX_BASE_URL, CACHE_TTL

@st.cache_data(ttl=CACHE_TTL)
def geocode_address(address: str, use_mapbox: bool = False) -> Optional[Tuple[float, float]]:
    """
    Geokoda en adress till koordinater
    
    Args:
        address: Adress att geokoda
        use_mapbox: Använd Mapbox istället för Nominatim
    
    Returns:
        (lat, lon) eller None vid fel
    """
    try:
        if use_mapbox and "MAPBOX_TOKEN" in st.secrets:
            url = f"{MAPBOX_BASE_URL}/mapbox.places/{address}.json"
            params = {
                "access_token": st.secrets["MAPBOX_TOKEN"],
                "limit": 1
            }
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get("features"):
                    coords = data["features"][0]["geometry"]["coordinates"]
                    return coords[1], coords[0]  # lon, lat -> lat, lon
        else:
            # Använd Nominatim
            url = f"{NOMINATIM_BASE_URL}/search"
            params = {
                "q": address,
                "format": "json",
                "limit": 1
            }
            headers = {"User-Agent": "StreamlitRunningApp/1.0"}
            response = requests.get(url, params=params, headers=headers, timeout=10)
            time.sleep(1)  # Rate limiting för Nominatim
            
            if response.status_code == 200:
                data = response.json()
                if data:
                    return float(data[0]["lat"]), float(data[0]["lon"])
    except Exception as e:
        st.error(f"Geokodningsfel: {str(e)}")
    return None

@st.cache_data(ttl=CACHE_TTL)
def reverse_geocode(lat: float, lon: float) -> Optional[str]:
    """
    Omvänd geokodning - koordinater till adress
    
    Args:
        lat: Latitud
        lon: Longitud
    
    Returns:
        Adress eller None vid fel
    """
    try:
        url = f"{NOMINATIM_BASE_URL}/reverse"
        params = {
            "lat": lat,
            "lon": lon,
            "format": "json"
        }
        headers = {"User-Agent": "StreamlitRunningApp/1.0"}
        response = requests.get(url, params=params, headers=headers, timeout=10)
        time.sleep(1)  # Rate limiting
        
        if response.status_code == 200:
            data = response.json()
            return data.get("display_name", "Okänd plats")
    except:
        pass
    return None