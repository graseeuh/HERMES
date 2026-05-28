from .geo_types import AssetType, EnergyAsset, ProximityFeature
from .hazard_analyzer import haversine_km

# Inherent physical security risk per asset type (0–1)
_ASSET_BASE_RISK: dict[AssetType, float] = {
    AssetType.POWER_LINE: 0.40,
    AssetType.SUBSTATION: 0.80,
    AssetType.TRANSFORMER: 0.70,
    AssetType.PIPELINE: 0.60,
    AssetType.REFINERY: 0.85,
    AssetType.STORAGE_FACILITY: 0.75,
    AssetType.SOLAR_FARM: 0.30,
    AssetType.WIND_TURBINE: 0.25,
    AssetType.OFFSHORE_PLATFORM: 0.70,
}
_DEFAULT_BASE_RISK = 0.50

_WEIGHTS = {
    "asset_type_risk": 0.35,
    "isolation_index": 0.25,
    "access_exposure": 0.20,
    "criticality": 0.20,
}


def _isolation_index(asset: EnergyAsset, settlements: list[ProximityFeature]) -> float:
    """
    0–1 isolation score. High isolation means harder to monitor and respond to.
    Distances: ≤5 km → 0.10 (well-covered), ≥50 km → 0.90 (very isolated).
    """
    if not settlements:
        return 0.80  # unknown: assume isolated
    min_dist = min(haversine_km(asset.location, s.location) for s in settlements)
    if min_dist <= 5.0:
        return 0.10
    if min_dist >= 50.0:
        return 0.90
    return 0.10 + (min_dist - 5.0) / 45.0 * 0.80


def analyze_security(
    asset: EnergyAsset,
    settlements: list[ProximityFeature] | None = None,
    access_route_count: int = 1,
) -> tuple[float, dict]:
    """
    Return (score 0–100, factors dict) for physical security risk.
    access_route_count: number of public access routes to the site (more = more exposure).
    asset.metadata['critical'] = True raises the criticality sub-score.
    """
    settlements = settlements or []
    base = _ASSET_BASE_RISK.get(asset.asset_type, _DEFAULT_BASE_RISK)
    isolation = _isolation_index(asset, settlements)
    access = min(access_route_count / 4.0, 1.0)
    criticality = 1.0 if asset.metadata.get("critical") else 0.50

    combined = (
        base * _WEIGHTS["asset_type_risk"]
        + isolation * _WEIGHTS["isolation_index"]
        + access * _WEIGHTS["access_exposure"]
        + criticality * _WEIGHTS["criticality"]
    )
    score = round(min(combined, 1.0) * 100, 2)
    factors = {
        "asset_type_risk": round(base, 3),
        "isolation_index": round(isolation, 3),
        "access_exposure": round(access, 3),
        "criticality": round(criticality, 3),
    }
    return score, factors
