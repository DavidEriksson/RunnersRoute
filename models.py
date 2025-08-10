"""
Datamodeller för löparruttplaneraren
"""

from dataclasses import dataclass
from datetime import timedelta
from typing import List, Optional

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
    provider: str = "ORS"  # Vilket API som användes