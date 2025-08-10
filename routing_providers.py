"""
Routing-providers: ORS och GraphHopper
"""

import streamlit as st
import requests
import random
from typing import Tuple, Optional, List
from datetime import timedelta
import math

from config import (
    ORS_BASE_URL, 
    GRAPHHOPPER_BASE_URL,
    MAX_ROUTE_ATTEMPTS,
    PERFECT_TOLERANCE_PERCENT
)
from models import RouteInfo, RoutePoint
from utils import calculate_elevation_gain, calculate_distance_from_points, parse_pace

class RoutingProvider:
    """Basklass för routing-providers"""
    
    def get_route(
        self,
        start: Tuple[float, float],
        end: Optional[Tuple[float, float]],
        distance_km: float,
        tolerance_percent: float,
        mode: str = "loop"
    ) -> Optional[RouteInfo]:
        raise NotImplementedError

class OpenRouteServiceProvider(RoutingProvider):
    """OpenRouteService routing provider"""
    
    def __init__(self):
        self.name = "ORS"
        
    def get_route(
        self,
        start: Tuple[float, float],
        end: Optional[Tuple[float, float]],
        distance_km: float,
        tolerance_percent: float,
        mode: str = "loop",
        seed: int = 0
    ) -> Optional[RouteInfo]:
        """Hämta rutt från OpenRouteService"""
        
        if "ORS_API_KEY" not in st.secrets:
            return None
            
        url = f"{ORS_BASE_URL}/v2/directions/foot-walking/geojson"
        headers = {
            "Authorization": st.secrets["ORS_API_KEY"],
            "Content-Type": "application/json"
        }
        
        distance_m = distance_km * 1000
        tolerance_m = distance_m * (tolerance_percent / 100)
        
        if mode == "loop":
            best_route = self._find_best_loop_route(
                start, distance_m, tolerance_m, headers, url, seed
            )
            if best_route:
                return self._parse_ors_response(best_route)
        else:
            # Point-to-point implementation
            if not end:
                return None
            route_data = self._get_point_to_point_route(
                start, end, distance_m, tolerance_m, headers, url
            )
            if route_data:
                return self._parse_ors_response(route_data)
        
        return None
    
    def _find_best_loop_route(
        self, 
        start: Tuple[float, float],
        distance_m: float,
        tolerance_m: float,
        headers: dict,
        url: str,
        seed: int
    ) -> Optional[dict]:
        """Hitta bästa loop-rutten genom att testa flera varianter"""
        
        best_route = None
        best_deviation = float('inf')
        attempts_info = []
        found_within_tolerance = False
        
        # Justera antal punkter baserat på distans
        num_points = min(5, max(2, int(distance_m / 2000)))
        
        for attempt in range(MAX_ROUTE_ATTEMPTS):
            route_seed = seed + attempt if seed > 0 else random.randint(1, 100000)
            
            body = {
                "coordinates": [[start[1], start[0]]],
                "elevation": True,
                "options": {
                    "round_trip": {
                        "length": distance_m,
                        "points": num_points,
                        "seed": route_seed
                    }
                }
            }
            
            try:
                response = requests.post(url, json=body, headers=headers, timeout=30)
                if response.status_code == 200:
                    data = response.json()
                    if "features" in data and data["features"]:
                        route_distance = data["features"][0]["properties"]["summary"]["distance"]
                        deviation = abs(route_distance - distance_m)
                        deviation_percent = ((route_distance - distance_m) / distance_m) * 100
                        
                        within_tolerance = deviation <= tolerance_m
                        status = "✓" if within_tolerance else ""
                        attempts_info.append(
                            f"ORS variant {attempt + 1}: {route_distance/1000:.2f} km ({deviation_percent:+.1f}%) {status}"
                        )
                        
                        if within_tolerance:
                            if not found_within_tolerance or deviation < best_deviation:
                                found_within_tolerance = True
                                best_deviation = deviation
                                best_route = data
                            if abs(deviation_percent) <= PERFECT_TOLERANCE_PERCENT:
                                break
                        elif not found_within_tolerance and deviation < best_deviation:
                            best_deviation = deviation
                            best_route = data
                
                if found_within_tolerance and attempt >= 2:
                    break
                    
            except Exception:
                continue
        
        # Visa resultat endast om debug mode
        if attempts_info and st.checkbox("Visa debug", value=False, key="debug_ors"):
            with st.expander(f"ORS testade {len(attempts_info)} varianter", expanded=False):
                for info in attempts_info:
                    st.text(info)
                if found_within_tolerance:
                    st.success(f"Hittade rutt inom tolerans ({tolerance_percent}%)")
                else:
                    st.warning("Ingen rutt inom tolerans hittades")
        
        return best_route
    
    def _get_point_to_point_route(
        self,
        start: Tuple[float, float],
        end: Tuple[float, float],
        distance_m: float,
        tolerance_m: float,
        headers: dict,
        url: str
    ) -> Optional[dict]:
        """Hämta point-to-point rutt"""
        
        body = {
            "coordinates": [[start[1], start[0]], [end[1], end[0]]],
            "elevation": True,
            "instructions": False
        }
        
        try:
            response = requests.post(url, json=body, headers=headers, timeout=30)
            if response.status_code == 200:
                return response.json()
        except Exception:
            pass
        
        return None
    
    def _parse_ors_response(self, data: dict) -> Optional[RouteInfo]:
        """Parsa ORS-respons till RouteInfo"""
        
        if "features" not in data or not data["features"]:
            return None
            
        feature = data["features"][0]
        geometry = feature.get("geometry", {})
        properties = feature.get("properties", {})
        
        coordinates = geometry.get("coordinates", [])
        points = []
        
        for coord in coordinates:
            if len(coord) >= 2:
                elevation = coord[2] if len(coord) > 2 else None
                points.append(RoutePoint(
                    lat=coord[1],
                    lon=coord[0],
                    elevation=elevation
                ))
        
        ascent = properties.get("ascent", 0)
        elevation_gain = ascent if ascent > 0 else calculate_elevation_gain(points)
        
        distance = properties.get("summary", {}).get("distance", 0)
        if distance == 0 and points:
            distance = calculate_distance_from_points(points)
        
        pace_min = parse_pace(st.session_state.get("pace", "5:30"))
        time_minutes = (distance / 1000) * pace_min
        
        return RouteInfo(
            points=points,
            distance=distance,
            elevation_gain=elevation_gain,
            estimated_time=timedelta(minutes=time_minutes),
            geometry=coordinates,
            provider="ORS"
        )

class GraphHopperProvider(RoutingProvider):
    """GraphHopper routing provider - ofta mer exakt för rundor"""
    
    def __init__(self):
        self.name = "GraphHopper"
        
    def get_route(
        self,
        start: Tuple[float, float],
        end: Optional[Tuple[float, float]],
        distance_km: float,
        tolerance_percent: float,
        mode: str = "loop",
        seed: int = 0
    ) -> Optional[RouteInfo]:
        """Hämta rutt från GraphHopper"""
        
        if "GRAPHHOPPER_API_KEY" not in st.secrets:
            return None
            
        distance_m = distance_km * 1000
        tolerance_m = distance_m * (tolerance_percent / 100)
        
        if mode == "loop":
            return self._get_round_trip(start, distance_m, tolerance_m, seed)
        else:
            if not end:
                return None
            return self._get_point_to_point(start, end)
    
    def _get_round_trip(
        self,
        start: Tuple[float, float],
        distance_m: float,
        tolerance_m: float,
        seed: int
    ) -> Optional[RouteInfo]:
        """Hämta round trip från GraphHopper"""
        
        url = f"{GRAPHHOPPER_BASE_URL}/route"
        
        best_route = None
        best_deviation = float('inf')
        attempts_info = []
        found_within_tolerance = False
        
        # Beräkna tolerance_percent från tolerance_m
        tolerance_percent = (tolerance_m / distance_m) * 100
        
        # GraphHopper har ofta bättre precision, så vi testar färre varianter
        max_attempts = 5
        
        for attempt in range(max_attempts):
            current_seed = seed + attempt if seed > 0 else random.randint(1, 100000)
            
            # GraphHopper tenderar att underestimera, så justera uppåt
            adjustment = 1.0 + (attempt * 0.05)  # 1.0, 1.05, 1.10, etc.
            adjusted_distance = distance_m * adjustment
            
            params = {
                "key": st.secrets["GRAPHHOPPER_API_KEY"],
                "point": f"{start[0]},{start[1]}",
                "vehicle": "foot",
                "algorithm": "round_trip",
                "round_trip.distance": int(adjusted_distance),
                "round_trip.seed": current_seed,
                "elevation": "true",
                "points_encoded": "false",
                "locale": "sv"
            }
            
            try:
                response = requests.get(url, params=params, timeout=30)
                if response.status_code == 200:
                    data = response.json()
                    if "paths" in data and data["paths"]:
                        path = data["paths"][0]
                        route_distance = path.get("distance", 0)
                        deviation = abs(route_distance - distance_m)
                        deviation_percent = ((route_distance - distance_m) / distance_m) * 100
                        
                        within_tolerance = deviation <= tolerance_m
                        status = "✓" if within_tolerance else ""
                        attempts_info.append(
                            f"GraphHopper variant {attempt + 1}: {route_distance/1000:.2f} km ({deviation_percent:+.1f}%) {status}"
                        )
                        
                        if within_tolerance:
                            if not found_within_tolerance or deviation < best_deviation:
                                found_within_tolerance = True
                                best_deviation = deviation
                                best_route = data
                            if abs(deviation_percent) <= PERFECT_TOLERANCE_PERCENT:
                                break
                        elif not found_within_tolerance and deviation < best_deviation:
                            best_deviation = deviation
                            best_route = data
                            
            except Exception as e:
                st.warning(f"GraphHopper fel: {str(e)}")
                continue
        
        # Visa resultat endast om debug mode
        if attempts_info and st.checkbox("Visa debug", value=False, key="debug_gh"):
            with st.expander(f"GraphHopper testade {len(attempts_info)} varianter", expanded=False):
                for info in attempts_info:
                    st.text(info)
                if found_within_tolerance:
                    st.success(f"Hittade rutt inom tolerans ({tolerance_percent}%)")
                else:
                    st.info("Ingen rutt inom tolerans hittades")
        
        if best_route:
            return self._parse_graphhopper_response(best_route)
        
        return None
    
    def _get_point_to_point(
        self,
        start: Tuple[float, float],
        end: Tuple[float, float]
    ) -> Optional[RouteInfo]:
        """Hämta point-to-point rutt från GraphHopper"""
        
        url = f"{GRAPHHOPPER_BASE_URL}/route"
        params = {
            "key": st.secrets["GRAPHHOPPER_API_KEY"],
            "point": [f"{start[0]},{start[1]}", f"{end[0]},{end[1]}"],
            "vehicle": "foot",
            "elevation": "true",
            "points_encoded": "false",
            "locale": "sv"
        }
        
        try:
            response = requests.get(url, params=params, timeout=30)
            if response.status_code == 200:
                return self._parse_graphhopper_response(response.json())
        except Exception:
            pass
        
        return None
    
    def _parse_graphhopper_response(self, data: dict) -> Optional[RouteInfo]:
        """Parsa GraphHopper-respons till RouteInfo"""
        
        if "paths" not in data or not data["paths"]:
            return None
        
        path = data["paths"][0]
        points_data = path.get("points", {})
        
        if "coordinates" not in points_data:
            return None
        
        coordinates = points_data["coordinates"]
        points = []
        
        for coord in coordinates:
            if len(coord) >= 2:
                # GraphHopper format: [lon, lat, elevation]
                elevation = coord[2] if len(coord) > 2 else None
                points.append(RoutePoint(
                    lat=coord[1],
                    lon=coord[0],
                    elevation=elevation
                ))
        
        distance = path.get("distance", 0)
        ascend = path.get("ascend", 0)
        elevation_gain = ascend if ascend > 0 else calculate_elevation_gain(points)
        
        # GraphHopper ger tid i millisekunder
        time_ms = path.get("time", 0)
        if time_ms > 0:
            estimated_time = timedelta(milliseconds=time_ms)
        else:
            pace_min = parse_pace(st.session_state.get("pace", "5:30"))
            time_minutes = (distance / 1000) * pace_min
            estimated_time = timedelta(minutes=time_minutes)
        
        return RouteInfo(
            points=points,
            distance=distance,
            elevation_gain=elevation_gain,
            estimated_time=estimated_time,
            geometry=coordinates,
            provider="GraphHopper"
        )