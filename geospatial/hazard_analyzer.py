import math
from .geo_types import Coordinate, EnergyAsset, HazardType, HazardZone

# Weights for each natural hazard type in the combined score
_HAZARD_WEIGHTS: dict[HazardType, float] = {
    HazardType.FLOOD: 0.35,
    HazardType.EARTHQUAKE: 0.30,
    HazardType.WILDFIRE: 0.20,
    HazardType.HURRICANE: 0.15,
}


def haversine_km(a: Coordinate, b: Coordinate) -> float:
    """Great-circle distance between two coordinates in kilometres."""
    R = 6371.0
    lat1, lon1 = math.radians(a.lat), math.radians(a.lon)
    lat2, lon2 = math.radians(b.lat), math.radians(b.lon)
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))


def _zone_exposure(asset: EnergyAsset, zones: list[HazardZone], hazard: HazardType) -> float:
    """
    0–1 exposure for one hazard type: max over all matching zones of
    (severity × linear proximity factor).  Zero if outside every zone.
    """
    best = 0.0
    for zone in zones:
        if zone.hazard_type != hazard:
            continue
        dist = haversine_km(asset.location, zone.center)
        if dist >= zone.radius_km:
            continue
        proximity_factor = 1.0 - (dist / zone.radius_km)
        best = max(best, zone.severity * proximity_factor)
    return best


def analyze_hazard(asset: EnergyAsset, hazard_zones: list[HazardZone]) -> tuple[float, dict]:
    """
    Return (score 0–100, factors dict) representing natural hazard risk.
    Score is a weighted sum of per-hazard exposures.
    """
    exposures = {h: _zone_exposure(asset, hazard_zones, h) for h in HazardType}
    combined = sum(exp * _HAZARD_WEIGHTS[h] for h, exp in exposures.items())
    score = round(combined * 100, 2)
    factors = {f"{h.value}_exposure": round(exp, 3) for h, exp in exposures.items()}
    return score, factors
