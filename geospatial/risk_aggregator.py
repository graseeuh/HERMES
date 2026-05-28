from .climate_analyzer import analyze_climate
from .geo_types import Coordinate, EnergyAsset, HazardZone, ProximityFeature, RiskLevel, RiskScore
from .hazard_analyzer import analyze_hazard
from .proximity_analyzer import analyze_proximity
from .security_analyzer import analyze_security

DEFAULT_WEIGHTS: dict[str, float] = {
    "hazard": 0.30,
    "climate": 0.25,
    "proximity": 0.25,
    "security": 0.20,
}


def _risk_level(score: float) -> RiskLevel:
    if score >= 80:
        return RiskLevel.CRITICAL
    if score >= 60:
        return RiskLevel.HIGH
    if score >= 40:
        return RiskLevel.MEDIUM
    if score >= 20:
        return RiskLevel.LOW
    return RiskLevel.MINIMAL


def score_asset(
    asset: EnergyAsset,
    hazard_zones: list[HazardZone] | None = None,
    proximity_features: list[ProximityFeature] | None = None,
    coastline_features: list[Coordinate] | None = None,
    settlements: list[ProximityFeature] | None = None,
    access_route_count: int = 1,
    weights: dict[str, float] | None = None,
) -> RiskScore:
    """Score a single asset across all four risk dimensions and return a RiskScore."""
    w = weights or DEFAULT_WEIGHTS

    h_score, h_factors = analyze_hazard(asset, hazard_zones or [])
    c_score, c_factors = analyze_climate(asset, coastline_features)
    p_score, p_factors = analyze_proximity(asset, proximity_features or [])
    s_score, s_factors = analyze_security(asset, settlements, access_route_count)

    composite = (
        h_score * w.get("hazard", 0.30)
        + c_score * w.get("climate", 0.25)
        + p_score * w.get("proximity", 0.25)
        + s_score * w.get("security", 0.20)
    )
    composite = round(composite, 2)

    return RiskScore(
        asset_id=asset.id,
        hazard_score=h_score,
        climate_score=c_score,
        proximity_score=p_score,
        security_score=s_score,
        composite_score=composite,
        risk_level=_risk_level(composite),
        factors={
            "hazard": h_factors,
            "climate": c_factors,
            "proximity": p_factors,
            "security": s_factors,
        },
    )


def score_portfolio(
    assets: list[EnergyAsset],
    hazard_zones: list[HazardZone] | None = None,
    proximity_features: list[ProximityFeature] | None = None,
    coastline_features: list[Coordinate] | None = None,
    settlements: list[ProximityFeature] | None = None,
    access_route_count: int = 1,
    weights: dict[str, float] | None = None,
) -> list[RiskScore]:
    """Score every asset in a portfolio, sharing the same environmental context."""
    return [
        score_asset(
            asset,
            hazard_zones=hazard_zones,
            proximity_features=proximity_features,
            coastline_features=coastline_features,
            settlements=settlements,
            access_route_count=access_route_count,
            weights=weights,
        )
        for asset in assets
    ]
