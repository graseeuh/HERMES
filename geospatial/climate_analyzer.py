from .geo_types import AssetType, Coordinate, EnergyAsset
from .hazard_analyzer import haversine_km

# Asset types with elevated heat sensitivity (cooling-dependent equipment)
_HEAT_SENSITIVE = {AssetType.TRANSFORMER, AssetType.SUBSTATION, AssetType.PIPELINE, AssetType.REFINERY}

# Weights for each climate sub-score
_WEIGHTS = {"heat_stress": 0.40, "drought_risk": 0.30, "sea_level_exposure": 0.30}


def _heat_stress(lat: float, asset_type: AssetType) -> float:
    """0–1 heat stress estimate from latitude band."""
    abs_lat = abs(lat)
    if abs_lat <= 30:
        base = 0.80
    elif abs_lat <= 45:
        base = 0.50
    elif abs_lat <= 60:
        base = 0.25
    else:
        base = 0.10
    return min(base * 1.2, 1.0) if asset_type in _HEAT_SENSITIVE else base


def _drought_risk(lat: float) -> float:
    """0–1 drought risk by latitude band (subtropical dry zones score highest)."""
    abs_lat = abs(lat)
    if 15 <= abs_lat <= 35:
        return 0.70
    if abs_lat > 60:
        return 0.20
    return 0.30


def _sea_level_exposure(location: Coordinate, coastline: list[Coordinate], check_radius_km: float = 50.0) -> float:
    """0–1 coastal proximity score; linear decay from 0 km to check_radius_km."""
    if not coastline:
        return 0.0
    min_dist = min(haversine_km(location, c) for c in coastline)
    if min_dist >= check_radius_km:
        return 0.0
    return 1.0 - (min_dist / check_radius_km)


def analyze_climate(
    asset: EnergyAsset,
    coastline_features: list[Coordinate] | None = None,
) -> tuple[float, dict]:
    """
    Return (score 0–100, factors dict) representing climate / weather risk.
    Offshore platforms are forced to maximum sea-level exposure.
    """
    coastline_features = coastline_features or []
    lat = asset.location.lat

    heat = _heat_stress(lat, asset.asset_type)
    drought = _drought_risk(lat)
    sea_level = _sea_level_exposure(asset.location, coastline_features)

    if asset.asset_type == AssetType.OFFSHORE_PLATFORM:
        sea_level = max(sea_level, 0.90)

    combined = (
        heat * _WEIGHTS["heat_stress"]
        + drought * _WEIGHTS["drought_risk"]
        + sea_level * _WEIGHTS["sea_level_exposure"]
    )
    score = round(min(combined, 1.0) * 100, 2)
    factors = {
        "heat_stress": round(heat, 3),
        "drought_risk": round(drought, 3),
        "sea_level_exposure": round(sea_level, 3),
    }
    return score, factors
