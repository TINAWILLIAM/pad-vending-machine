"""
location_utils.py – Haversine distance calculation and nearest-machine finder
"""
import math
from typing import Any


def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Return the great-circle distance (km) between two GPS coordinates
    using the Haversine formula.
    """
    R = 6371.0  # Earth radius in kilometres
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def find_nearest_machine(user_lat: float, user_lon: float, machines: list[dict[str, Any]]) -> dict[str, Any] | None:
    """
    Given a list of machine documents (each must have 'location.latitude' and
    'location.longitude'), return the document of the nearest online machine.
    Returns None if no machines are available.
    """
    best: dict | None = None
    best_dist = float("inf")

    for machine in machines:
        loc = machine.get("location", {})
        m_lat = machine.get("latitude") or loc.get("latitude")
        m_lon = machine.get("longitude") or loc.get("longitude")
        if m_lat is None or m_lon is None:
            continue
        dist = haversine_distance_km(user_lat, user_lon, m_lat, m_lon)
        if dist < best_dist:
            best_dist = dist
            best = machine

    if best:
        best["distance_km"] = round(best_dist, 3)
    return best
