"""
Streamlit Running Route App
En komplett löparapp med ruttplanering, GPX-export och höjddata
"""

import streamlit as st
import folium
from streamlit_folium import st_folium
import requests
import gpxpy
import gpxpy.gpx
from datetime import datetime, timedelta
import json
import math
from typing import List, Tuple, Dict, Optional, Any
import time
from dataclasses import dataclass
import hashlib

# Konfiguration
DEFAULT_DISTANCE = 5.0
DEFAULT_TOLERANCE = 5.0
DEFAULT_PACE = "5:30"
DEFAULT_CENTER = [59.3293, 18.0686]  # Stockholm

# API URLs
ORS_BASE_URL = "https://api.openrouteservice.org"
NOMINATIM_BASE_URL = "https://nominatim.openstreetmap.org"
MAPBOX_BASE_URL = "https://api.mapbox.com/geocoding/v6"

@dataclass
class RoutePoint:
    """Representerar en punkt på rutten"""
    lat: float
    lon: float
    elevation: Optional[float] = None

@dataclass
class RouteInfo:
    """Information om en rutt"""
    points: List[RoutePoint]
    distance: float  # meter
    elevation_gain: float  # meter
    estimated_time: timedelta
    geometry: List[List[float]]

# Cache-funktioner
@st.cache_data(ttl=3600)
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

@st.cache_data(ttl=3600)
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

def create_cache_key(coordinates: List[List[float]], distance: float, 
                    mode: str, tolerance: float) -> str:
    """Skapa cache-nyckel för routing"""
    key_str = f"{coordinates}_{distance}_{mode}_{tolerance}"
    return hashlib.md5(key_str.encode()).hexdigest()

@st.cache_data(ttl=3600)
def get_route_ors(start: Tuple[float, float], 
                  end: Optional[Tuple[float, float]], 
                  distance_km: float,
                  tolerance_percent: float,
                  mode: str = "loop",
                  _cache_key: str = "") -> Optional[RouteInfo]:
    """
    Hämta rutt från OpenRouteService
    
    Args:
        start: (lat, lon) för startpunkt
        end: (lat, lon) för slutpunkt (endast point-to-point)
        distance_km: Önskad distans i km
        tolerance_percent: Tolerans i procent
        mode: "loop" eller "point-to-point"
        _cache_key: Cache-nyckel (används av Streamlit)
    
    Returns:
        RouteInfo eller None vid fel
    """
    if "ORS_API_KEY" not in st.secrets:
        st.error("ORS API-nyckel saknas i secrets!")
        return None
    
    try:
        url = f"{ORS_BASE_URL}/v2/directions/foot-walking/geojson"
        headers = {
            "Authorization": st.secrets["ORS_API_KEY"],
            "Content-Type": "application/json",
            "Accept": "application/json, application/geo+json, application/gpx+xml, img/png; charset=utf-8"
        }
        
        distance_m = distance_km * 1000
        tolerance_m = distance_m * (tolerance_percent / 100)
        
        if mode == "loop":
            # Round trip
            body = {
                "coordinates": [[start[1], start[0]]],  # lon, lat
                "elevation": True,
                "options": {
                    "round_trip": {
                        "length": distance_m,
                        "points": 3,
                        "seed": 42
                    }
                }
            }
        else:
            # Point-to-point
            if not end:
                return None
            
            # Börja med direkt rutt
            coordinates = [[start[1], start[0]], [end[1], end[0]]]
            body = {
                "coordinates": coordinates,
                "elevation": True,
                "instructions": False
            }
        
        # Första försöket
        response = requests.post(url, json=body, headers=headers, timeout=30)
        
        if response.status_code != 200:
            error_msg = f"ORS API fel: {response.status_code}"
            try:
                error_data = response.json()
                if "error" in error_data:
                    error_msg += f" - {error_data.get('error', {}).get('message', 'Okänt fel')}"
            except:
                error_msg += f" - {response.text[:200]}"
            st.error(error_msg)
            return None
        
        data = response.json()
        
        # Kontrollera att vi har rätt datastruktur
        if "features" not in data or not data["features"]:
            st.error("Ogiltig respons från ORS API - inga rutter hittades")
            return None
        
        feature = data["features"][0]
        
        # För point-to-point: kolla om vi behöver via-punkter
        if mode == "point-to-point" and "properties" in feature:
            current_distance = feature["properties"].get("summary", {}).get("distance", 0)
            
            # Om distansen inte är inom tolerans, lägg till via-punkter
            if abs(current_distance - distance_m) > tolerance_m:
                via_points = calculate_via_points(start, end, distance_m, current_distance)
                
                for via in via_points[:2]:  # Max 2 via-punkter
                    coordinates = [[start[1], start[0]], [via[1], via[0]], [end[1], end[0]]]
                    body["coordinates"] = coordinates
                    
                    response = requests.post(url, json=body, headers=headers, timeout=30)
                    if response.status_code == 200:
                        data = response.json()
                        if "features" in data and data["features"]:
                            feature = data["features"][0]
                            current_distance = feature.get("properties", {}).get("summary", {}).get("distance", 0)
                            
                            if abs(current_distance - distance_m) <= tolerance_m:
                                break
        
        # Extrahera ruttinformation från GeoJSON
        if "features" in data and data["features"]:
            feature = data["features"][0]
            geometry = feature.get("geometry", {})
            properties = feature.get("properties", {})
            
            # Hämta koordinater
            coordinates = geometry.get("coordinates", [])
            
            # Skapa RoutePoint-objekt
            points = []
            
            # Kontrollera om vi har höjddata i properties
            ascent = properties.get("ascent", 0)
            
            for coord in coordinates:
                # GeoJSON format: [lon, lat, elevation(optional)]
                if len(coord) >= 2:
                    elevation = coord[2] if len(coord) > 2 else None
                    points.append(RoutePoint(
                        lat=coord[1],
                        lon=coord[0],
                        elevation=elevation
                    ))
            
            # Använd ascent från properties om tillgänglig, annars beräkna
            elevation_gain = ascent if ascent > 0 else calculate_elevation_gain(points)
            
            # Beräkna tid baserat på tempo
            distance = properties.get("summary", {}).get("distance", 0)
            if distance == 0 and points:
                # Fallback: beräkna distans från punkter om den saknas
                distance = calculate_distance_from_points(points)
            
            pace_min = parse_pace(st.session_state.get("pace", DEFAULT_PACE))
            time_minutes = (distance / 1000) * pace_min
            estimated_time = timedelta(minutes=time_minutes)
            
            return RouteInfo(
                points=points,
                distance=distance,
                elevation_gain=elevation_gain,
                estimated_time=estimated_time,
                geometry=coordinates
            )
        else:
            st.error("Kunde inte extrahera ruttdata från API-svaret")
            return None
    
    except requests.exceptions.RequestException as e:
        st.error(f"Nätverksfel: {str(e)}")
    except json.JSONDecodeError as e:
        st.error(f"Kunde inte tolka API-svar: {str(e)}")
    except Exception as e:
        st.error(f"Routing fel: {str(e)}")
        # Debug info
        if st.checkbox("Visa debug-information"):
            st.code(f"Fel: {str(e)}\nTyp: {type(e)}")
    
    return None

def calculate_distance_from_points(points: List[RoutePoint]) -> float:
    """
    Beräkna total distans från en lista av punkter (fallback)
    
    Args:
        points: Lista med RoutePoint
    
    Returns:
        Total distans i meter
    """
    if len(points) < 2:
        return 0
    
    total_distance = 0
    for i in range(len(points) - 1):
        # Haversine formula (förenklad)
        lat1, lon1 = math.radians(points[i].lat), math.radians(points[i].lon)
        lat2, lon2 = math.radians(points[i+1].lat), math.radians(points[i+1].lon)
        
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))
        
        # Jordens radie i meter
        r = 6371000
        total_distance += r * c
    
    return total_distance

def calculate_via_points(start: Tuple[float, float], 
                        end: Tuple[float, float],
                        target_distance: float,
                        current_distance: float) -> List[Tuple[float, float]]:
    """
    Beräkna via-punkter för att nå måldistans
    
    Args:
        start: Startpunkt (lat, lon)
        end: Slutpunkt (lat, lon)
        target_distance: Måldistans i meter
        current_distance: Nuvarande distans i meter
    
    Returns:
        Lista med via-punkter
    """
    # Beräkna mittpunkt
    mid_lat = (start[0] + end[0]) / 2
    mid_lon = (start[1] + end[1]) / 2
    
    # Behöver vi lägga till distans?
    need_more = target_distance > current_distance
    
    # Beräkna radie baserat på hur mycket extra distans vi behöver
    extra_distance = abs(target_distance - current_distance)
    radius = extra_distance / (2 * math.pi)  # Ungefärlig radie
    
    # Konvertera till lat/lon offset (grov approximation)
    lat_offset = radius / 111000  # ~111km per latitudgrad
    lon_offset = radius / (111000 * math.cos(math.radians(mid_lat)))
    
    via_points = []
    
    # Testa olika vinklar
    for angle in [0, 90, 180, 270]:
        rad = math.radians(angle)
        via_lat = mid_lat + lat_offset * math.sin(rad)
        via_lon = mid_lon + lon_offset * math.cos(rad)
        via_points.append((via_lat, via_lon))
    
    return via_points

def calculate_elevation_gain(points: List[RoutePoint]) -> float:
    """
    Beräkna total höjdökning
    
    Args:
        points: Lista med RoutePoint
    
    Returns:
        Total höjdökning i meter
    """
    if not points or not any(p.elevation for p in points):
        return 0.0
    
    total_gain = 0.0
    prev_elevation = None
    
    for point in points:
        if point.elevation is not None:
            if prev_elevation is not None and point.elevation > prev_elevation:
                total_gain += point.elevation - prev_elevation
            prev_elevation = point.elevation
    
    return total_gain

def parse_pace(pace_str: str) -> float:
    """
    Konvertera tempo-sträng till minuter per km
    
    Args:
        pace_str: Tempo som "5:30"
    
    Returns:
        Minuter per km
    """
    try:
        parts = pace_str.split(":")
        if len(parts) == 2:
            minutes = int(parts[0])
            seconds = int(parts[1])
            return minutes + seconds / 60
    except:
        pass
    return 5.5  # Default

def create_gpx(route_info: RouteInfo, name: str = "Löprunda") -> str:
    """
    Skapa GPX-fil från ruttinformation
    
    Args:
        route_info: RouteInfo-objekt
        name: Namn på rutten
    
    Returns:
        GPX som sträng
    """
    gpx = gpxpy.gpx.GPX()
    
    # Skapa track
    gpx_track = gpxpy.gpx.GPXTrack()
    gpx_track.name = name
    gpx.tracks.append(gpx_track)
    
    # Skapa segment
    gpx_segment = gpxpy.gpx.GPXTrackSegment()
    gpx_track.segments.append(gpx_segment)
    
    # Lägg till punkter
    for point in route_info.points:
        gpx_point = gpxpy.gpx.GPXTrackPoint(
            point.lat, 
            point.lon,
            elevation=point.elevation
        )
        gpx_segment.points.append(gpx_point)
    
    return gpx.to_xml()

def create_map(center: List[float], 
               route_info: Optional[RouteInfo] = None,
               start_marker: Optional[Tuple[float, float]] = None,
               end_marker: Optional[Tuple[float, float]] = None) -> folium.Map:
    """
    Skapa Folium-karta med rutt och markörer
    
    Args:
        center: Kartans centrum [lat, lon]
        route_info: Ruttinformation
        start_marker: Startmarkör (lat, lon)
        end_marker: Slutmarkör (lat, lon)
    
    Returns:
        Folium Map-objekt
    """
    m = folium.Map(
        location=center,
        zoom_start=13,
        control_scale=True
    )
    
    # Lägg till startmarkör
    if start_marker:
        folium.Marker(
            start_marker,
            popup="Start",
            icon=folium.Icon(color="green", icon="play")
        ).add_to(m)
    
    # Lägg till slutmarkör
    if end_marker:
        folium.Marker(
            end_marker,
            popup="Mål",
            icon=folium.Icon(color="red", icon="stop")
        ).add_to(m)
    
    # Rita rutt
    if route_info and route_info.points:
        route_coords = [[p.lat, p.lon] for p in route_info.points]
        folium.PolyLine(
            route_coords,
            color="blue",
            weight=4,
            opacity=0.8
        ).add_to(m)
        
        # Anpassa zoom för att visa hela rutten
        if len(route_coords) > 1:
            bounds = [[min(p[0] for p in route_coords), min(p[1] for p in route_coords)],
                     [max(p[0] for p in route_coords), max(p[1] for p in route_coords)]]
            m.fit_bounds(bounds)
    
    return m

def init_session_state():
    """Initiera session state"""
    if "start_coords" not in st.session_state:
        st.session_state.start_coords = None
    if "end_coords" not in st.session_state:
        st.session_state.end_coords = None
    if "distance" not in st.session_state:
        st.session_state.distance = DEFAULT_DISTANCE
    if "mode" not in st.session_state:
        st.session_state.mode = "loop"
    if "tolerance" not in st.session_state:
        st.session_state.tolerance = DEFAULT_TOLERANCE
    if "pace" not in st.session_state:
        st.session_state.pace = DEFAULT_PACE
    if "route_info" not in st.session_state:
        st.session_state.route_info = None
    if "map_click_mode" not in st.session_state:
        st.session_state.map_click_mode = "start"

def main():
    """Huvudfunktion för Streamlit-appen"""
    st.set_page_config(
        page_title="Löparruttplanerare",
        page_icon="🏃",
        layout="wide"
    )
    
    init_session_state()
    
    st.title("Löparruttplanerare")
    st.markdown("Planera din perfekta löprunda med exakt distans och GPX-export")
    
    # Sidebar för inställningar
    with st.sidebar:
        st.header("Inställningar")
        
        # Lägesval
        mode = st.radio(
            "Ruttläge",
            ["loop", "point-to-point"],
            format_func=lambda x: "Loop (start = mål)" if x == "loop" else "Point-to-point",
            key="mode"
        )
        
        # Distans
        distance = st.number_input(
            "Distans (km)",
            min_value=0.5,
            max_value=50.0,
            value=st.session_state.distance,
            step=0.5,
            key="distance"
        )
        
        # Tolerans
        tolerance = st.slider(
            "Tolerans (%)",
            min_value=1.0,
            max_value=20.0,
            value=st.session_state.tolerance,
            step=1.0,
            key="tolerance",
            help="Hur mycket rutten får avvika från önskad distans"
        )
        
        # Tempo
        pace = st.text_input(
            "Tempo (min/km)",
            value=st.session_state.pace,
            key="pace",
            help="Format: MM:SS, t.ex. 5:30"
        )
        
        st.divider()
        
        # Startpunkt
        st.subheader("Startpunkt")
        start_method = st.radio(
            "Välj metod",
            ["address", "map"],
            format_func=lambda x: "Adress" if x == "address" else "Klick på karta",
            key="start_method"
        )
        
        if start_method == "address":
            start_address = st.text_input(
                "Startadress",
                placeholder="T.ex. Kungsgatan 1, Stockholm",
                key="start_address"
            )
            if st.button("Geokoda start", key="geocode_start"):
                coords = geocode_address(start_address)
                if coords:
                    st.session_state.start_coords = coords
                    st.success(f"Startpunkt: {coords[0]:.4f}, {coords[1]:.4f}")
                else:
                    st.error("Kunde inte hitta adressen")
        
        # Slutpunkt för point-to-point
        if mode == "point-to-point":
            st.divider()
            st.subheader("Slutpunkt")
            end_method = st.radio(
                "Välj metod",
                ["address", "map"],
                format_func=lambda x: "Adress" if x == "address" else "Klick på karta",
                key="end_method"
            )
            
            if end_method == "address":
                end_address = st.text_input(
                    "Slutadress",
                    placeholder="T.ex. Stureplan, Stockholm",
                    key="end_address"
                )
                if st.button("Geokoda slut", key="geocode_end"):
                    coords = geocode_address(end_address)
                    if coords:
                        st.session_state.end_coords = coords
                        st.success(f"Slutpunkt: {coords[0]:.4f}, {coords[1]:.4f}")
                    else:
                        st.error("Kunde inte hitta adressen")
        
        st.divider()
        
        # Generera rutt
        if st.button("Generera rutt", type="primary", use_container_width=True):
            if not st.session_state.start_coords:
                st.error("Välj en startpunkt först!")
            elif mode == "point-to-point" and not st.session_state.end_coords:
                st.error("Välj en slutpunkt först!")
            else:
                with st.spinner("Beräknar rutt..."):
                    # Skapa cache-nyckel
                    coords = [[st.session_state.start_coords[1], st.session_state.start_coords[0]]]
                    if mode == "point-to-point":
                        coords.append([st.session_state.end_coords[1], st.session_state.end_coords[0]])
                    
                    cache_key = create_cache_key(coords, distance, mode, tolerance)
                    
                    route_info = get_route_ors(
                        st.session_state.start_coords,
                        st.session_state.end_coords if mode == "point-to-point" else None,
                        distance,
                        tolerance,
                        mode,
                        cache_key
                    )
                    
                    if route_info:
                        st.session_state.route_info = route_info
                        st.success("Rutt genererad!")
                    else:
                        st.error("Kunde inte generera rutt. Försök justera inställningarna.")
    
    # Huvudinnehåll
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("Karta")
        
        # Info om klickläge
        if st.session_state.mode == "point-to-point":
            click_mode = st.radio(
                "Klickläge",
                ["start", "end"],
                format_func=lambda x: "Sätt startpunkt" if x == "start" else "Sätt slutpunkt",
                horizontal=True,
                key="map_click_mode"
            )
        
        # Skapa karta
        center = list(st.session_state.start_coords) if st.session_state.start_coords else DEFAULT_CENTER
        
        m = create_map(
            center,
            st.session_state.route_info,
            st.session_state.start_coords,
            st.session_state.end_coords if st.session_state.mode == "point-to-point" else None
        )
        
        # Visa karta med interaktion
        map_data = st_folium(
            m,
            key="map",
            width=None,
            height=500,
            returned_objects=["last_object_clicked_coords"]
        )
        
        # Hantera kartklick
        if map_data and "last_object_clicked_coords" in map_data and map_data["last_object_clicked_coords"]:
            clicked = map_data["last_object_clicked_coords"]
            coords = (clicked["lat"], clicked["lng"])
            
            if st.session_state.map_click_mode == "start" or st.session_state.mode == "loop":
                st.session_state.start_coords = coords
                address = reverse_geocode(coords[0], coords[1])
                st.info(f"Startpunkt satt: {address or f'{coords[0]:.4f}, {coords[1]:.4f}'}")
            else:
                st.session_state.end_coords = coords
                address = reverse_geocode(coords[0], coords[1])
                st.info(f"Slutpunkt satt: {address or f'{coords[0]:.4f}, {coords[1]:.4f}'}")
    
    with col2:
        st.subheader("Sammanfattning")
        
        if st.session_state.route_info:
            route = st.session_state.route_info
            
            # Visa statistik
            st.metric("Distans", f"{route.distance/1000:.2f} km")
            st.metric("Höjdökning", f"{route.elevation_gain:.0f} m")
            st.metric("Uppskattad tid", str(route.estimated_time).split('.')[0])
            
            # Toleransinfo
            target_distance = st.session_state.distance * 1000
            deviation = ((route.distance - target_distance) / target_distance) * 100
            if abs(deviation) <= st.session_state.tolerance:
                st.success(f"Inom tolerans: {deviation:+.1f}%")
            else:
                st.warning(f"Utanför tolerans: {deviation:+.1f}%")
            
            st.divider()
            
            # GPX-export
            st.subheader("Export")
            
            gpx_name = st.text_input(
                "Ruttnamn",
                value=f"Löprunda {datetime.now().strftime('%Y-%m-%d')}",
                key="gpx_name"
            )
            
            if st.button("Ladda ner GPX", use_container_width=True):
                gpx_content = create_gpx(route, gpx_name)
                st.download_button(
                    label="Spara GPX-fil",
                    data=gpx_content,
                    file_name=f"{gpx_name.replace(' ', '_')}.gpx",
                    mime="application/gpx+xml",
                    use_container_width=True
                )
        else:
            st.info("Generera en rutt för att se sammanfattning")
    
    # Footer
    st.divider()
    st.markdown(
        """
        <div style='text-align: center; color: gray; font-size: 0.8em;'>
        Skapad för löpare | 
        Använder OpenRouteService, OpenStreetMap & Streamlit
        </div>
        """,
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()