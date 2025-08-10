"""
Hjälpfunktioner för löparruttplaneraren
"""

import math
import gpxpy
import gpxpy.gpx
from typing import List, Tuple
from datetime import datetime
from models import RoutePoint, RouteInfo

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

def calculate_distance_from_points(points: List[RoutePoint]) -> float:
    """
    Beräkna total distans från en lista av punkter (Haversine formula)
    
    Args:
        points: Lista med RoutePoint
    
    Returns:
        Total distans i meter
    """
    if len(points) < 2:
        return 0
    
    total_distance = 0
    for i in range(len(points) - 1):
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
    
    # Lägg till metadata
    gpx.creator = "Löparruttplanerare"
    gpx.description = f"Genererad löprunda på {route_info.distance/1000:.2f} km"
    
    # Skapa track
    gpx_track = gpxpy.gpx.GPXTrack()
    gpx_track.name = name
    gpx_track.type = "running"
    gpx.tracks.append(gpx_track)
    
    # Skapa segment
    gpx_segment = gpxpy.gpx.GPXTrackSegment()
    gpx_track.segments.append(gpx_segment)
    
    # Lägg till punkter
    for point in route_info.points:
        gpx_point = gpxpy.gpx.GPXTrackPoint(
            point.lat, 
            point.lon,
            elevation=point.elevation,
            time=datetime.now()  # Kan förbättras med faktisk tidsstämpel
        )
        gpx_segment.points.append(gpx_point)
    
    # Lägg till statistik som extensions
    if route_info.elevation_gain > 0:
        gpx_track.description = f"Höjdökning: {route_info.elevation_gain:.0f}m, Uppskattad tid: {route_info.estimated_time}"
    
    return gpx.to_xml()

def calculate_via_points(
    start: Tuple[float, float], 
    end: Tuple[float, float],
    target_distance: float,
    current_distance: float
) -> List[Tuple[float, float]]:
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

def format_time(minutes: float) -> str:
    """
    Formatera tid från minuter till sträng
    
    Args:
        minutes: Antal minuter
    
    Returns:
        Formaterad tidssträng (HH:MM:SS eller MM:SS)
    """
    hours = int(minutes // 60)
    mins = int(minutes % 60)
    secs = int((minutes * 60) % 60)
    
    if hours > 0:
        return f"{hours:02d}:{mins:02d}:{secs:02d}"
    else:
        return f"{mins:02d}:{secs:02d}"

def calculate_bearing(point1: Tuple[float, float], point2: Tuple[float, float]) -> float:
    """
    Beräkna bäring mellan två punkter
    
    Args:
        point1: Startpunkt (lat, lon)
        point2: Slutpunkt (lat, lon)
    
    Returns:
        Bäring i grader (0-360)
    """
    lat1, lon1 = math.radians(point1[0]), math.radians(point1[1])
    lat2, lon2 = math.radians(point2[0]), math.radians(point2[1])
    
    dlon = lon2 - lon1
    
    y = math.sin(dlon) * math.cos(lat2)
    x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
    
    bearing = math.atan2(y, x)
    bearing = math.degrees(bearing)
    bearing = (bearing + 360) % 360
    
    return bearing

def get_compass_direction(bearing: float) -> str:
    """
    Konvertera bäring till kompassriktning
    
    Args:
        bearing: Bäring i grader
    
    Returns:
        Kompassriktning (N, NE, E, etc.)
    """
    directions = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
                  "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
    index = int((bearing + 11.25) / 22.5) % 16
    return directions[index]

def validate_coordinates(lat: float, lon: float) -> bool:
    """
    Validera att koordinater är giltiga
    
    Args:
        lat: Latitud
        lon: Longitud
    
    Returns:
        True om koordinaterna är giltiga
    """
    return -90 <= lat <= 90 and -180 <= lon <= 180

def get_route_statistics(route_info: RouteInfo) -> dict:
    """
    Beräkna detaljerad statistik för en rutt
    
    Args:
        route_info: RouteInfo-objekt
    
    Returns:
        Dictionary med statistik
    """
    stats = {
        "distance_km": route_info.distance / 1000,
        "distance_m": route_info.distance,
        "elevation_gain": route_info.elevation_gain,
        "elevation_loss": 0,
        "max_elevation": None,
        "min_elevation": None,
        "estimated_time": route_info.estimated_time,
        "num_points": len(route_info.points),
        "provider": route_info.provider
    }
    
    # Beräkna höjdstatistik
    elevations = [p.elevation for p in route_info.points if p.elevation is not None]
    if elevations:
        stats["max_elevation"] = max(elevations)
        stats["min_elevation"] = min(elevations)
        
        # Beräkna höjdförlust
        prev_elevation = None
        for elevation in elevations:
            if prev_elevation is not None and elevation < prev_elevation:
                stats["elevation_loss"] += prev_elevation - elevation
            prev_elevation = elevation
    
    return stats