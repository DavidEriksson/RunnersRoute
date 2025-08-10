"""
Kartfunktioner för visualisering
"""

import folium
from typing import List, Optional, Tuple
from models import RouteInfo

def create_map(
    center: List[float], 
    route_info: Optional[RouteInfo] = None,
    start_marker: Optional[Tuple[float, float]] = None,
    end_marker: Optional[Tuple[float, float]] = None
) -> folium.Map:
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
        
        # Olika färger beroende på provider
        color_map = {
            "ORS": "blue",
            "GraphHopper": "purple"
        }
        color = color_map.get(route_info.provider, "blue")
        
        folium.PolyLine(
            route_coords,
            color=color,
            weight=4,
            opacity=0.8,
            popup=f"{route_info.provider}: {route_info.distance/1000:.2f} km"
        ).add_to(m)
        
        # Anpassa zoom för att visa hela rutten
        if len(route_coords) > 1:
            bounds = [[min(p[0] for p in route_coords), min(p[1] for p in route_coords)],
                     [max(p[0] for p in route_coords), max(p[1] for p in route_coords)]]
            m.fit_bounds(bounds)
    
    return m