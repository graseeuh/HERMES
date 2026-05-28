from .geo_types import EnergyAsset, ProximityFeature
from .hazard_analyzer import haversine_km

# Category weights: how much each feature type contributes to proximity risk
_CATEGORY_WEIGHTS: dict[str, float] = {
    "population_center": 0.40,
    "hospital": 0.20,
    "school": 0.15,
    "military": 0.15,
    "water_treatment": 0.10,
}
_MAX_POSSIBLE = sum(_CATEGORY_WEIGHTS.values())  # normalisation denominator
_DEFAULT_CATEGORY_WEIGHT = 0.10


def _overlap_score(asset: EnergyAsset, feature: ProximityFeature) -> float:
    """0–1 raw overlap: proximity factor × feature weight."""
    dist = haversine_km(asset.location, feature.location)
    if dist >= feature.radius_km:
        return 0.0
    return (1.0 - dist / feature.radius_km) * feature.weight


def analyze_proximity(asset: EnergyAsset, features: list[ProximityFeature]) -> tuple[float, dict]:
    """
    Return (score 0–100, factors dict) for infrastructure proximity risk.
    Per category we keep the highest single-feature overlap, then weight by category.
    """
    best_by_type: dict[str, float] = {}
    for feat in features:
        raw = _overlap_score(asset, feat)
        if raw > 0:
            prev = best_by_type.get(feat.feature_type, 0.0)
            best_by_type[feat.feature_type] = max(prev, raw)

    total = sum(
        v * _CATEGORY_WEIGHTS.get(ftype, _DEFAULT_CATEGORY_WEIGHT)
        for ftype, v in best_by_type.items()
    )
    normalized = min(total / _MAX_POSSIBLE, 1.0) if _MAX_POSSIBLE > 0 else 0.0
    score = round(normalized * 100, 2)
    factors = {k: round(v, 3) for k, v in best_by_type.items()}
    return score, factors
