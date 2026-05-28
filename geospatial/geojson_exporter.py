import json
from .geo_types import EnergyAsset, RiskScore

_RISK_COLORS: dict[str, str] = {
    "critical": "#d32f2f",
    "high": "#f57c00",
    "medium": "#fbc02d",
    "low": "#388e3c",
    "minimal": "#1976d2",
}


def _asset_feature(asset: EnergyAsset, score: RiskScore | None = None) -> dict:
    props: dict = {
        "id": asset.id,
        "name": asset.name,
        "asset_type": asset.asset_type.value,
        **asset.metadata,
    }
    if score is not None:
        props.update(
            {
                "risk_composite": score.composite_score,
                "risk_level": score.risk_level.value,
                "risk_hazard": score.hazard_score,
                "risk_climate": score.climate_score,
                "risk_proximity": score.proximity_score,
                "risk_security": score.security_score,
                "marker_color": _RISK_COLORS.get(score.risk_level.value, "#9e9e9e"),
            }
        )
    return {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            # GeoJSON uses [longitude, latitude]
            "coordinates": [asset.location.lon, asset.location.lat],
        },
        "properties": props,
    }


def export_portfolio(
    assets: list[EnergyAsset],
    scores: list[RiskScore] | None = None,
) -> dict:
    """
    Build a GeoJSON FeatureCollection for a portfolio.
    If scores are supplied, risk properties are embedded in each feature.
    """
    score_map = {s.asset_id: s for s in scores} if scores else {}
    return {
        "type": "FeatureCollection",
        "features": [_asset_feature(a, score_map.get(a.id)) for a in assets],
    }


def to_json(geojson: dict, indent: int = 2) -> str:
    return json.dumps(geojson, indent=indent)
