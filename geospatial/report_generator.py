import json
from datetime import datetime, timezone
from .geo_types import EnergyAsset, RiskLevel, RiskScore

_MITIGATIONS: dict[str, str] = {
    "flood_exposure": "Install flood barriers and elevate critical equipment above 100-year flood level.",
    "earthquake_exposure": "Retrofit to seismic zone standards; install shock-isolation mounts on sensitive equipment.",
    "wildfire_exposure": "Establish defensible perimeter; use fire-resistant enclosures and non-combustible cable trays.",
    "hurricane_exposure": "Harden structure to Category 4+ wind standards; pre-position spare transformers regionally.",
    "heat_stress": "Upgrade cooling systems; implement thermal derating during peak heat events.",
    "drought_risk": "Deploy water-recycling cooling loops; identify alternative cooling sources.",
    "sea_level_exposure": "Raise critical switchgear above projected 2100 flood levels; install tidal surge barriers.",
    "population_center": "Enhance blast containment; coordinate with local emergency management for exclusion zones.",
    "hospital": "Prioritise dedicated backup power feed; establish sub-30-minute restoration SLA.",
    "school": "Create site exclusion zone safety plan; coordinate shelter-in-place procedures.",
    "military": "Coordinate security protocols with adjacent military authority; restrict public access.",
    "water_treatment": "Establish redundant grid feed; prioritise restoration in outage sequencing.",
    "asset_type_risk": "Apply ICS-CERT physical security baseline: perimeter fencing, CCTV, motion detection.",
    "isolation_index": "Deploy remote asset monitoring with automatic alerting; pre-position response equipment.",
    "access_exposure": "Reduce public access points; implement anti-vehicle barriers and perimeter intrusion detection.",
    "criticality": "Ensure N-1 redundancy; document and rehearse emergency restoration procedures.",
}


def _top_factors(score: RiskScore, n: int = 3) -> list[tuple[str, float]]:
    flat: dict[str, float] = {}
    for factors in score.factors.values():
        for k, v in factors.items():
            flat[k] = float(v)
    return sorted(flat.items(), key=lambda x: x[1], reverse=True)[:n]


def generate_asset_report(asset: EnergyAsset, score: RiskScore) -> dict:
    top = _top_factors(score)
    return {
        "asset_id": asset.id,
        "asset_name": asset.name,
        "asset_type": asset.asset_type.value,
        "location": {"lat": asset.location.lat, "lon": asset.location.lon},
        "risk_summary": {
            "composite_score": score.composite_score,
            "risk_level": score.risk_level.value,
            "hazard_score": score.hazard_score,
            "climate_score": score.climate_score,
            "proximity_score": score.proximity_score,
            "security_score": score.security_score,
        },
        "top_risk_factors": [{"factor": k, "value": round(v, 3)} for k, v in top],
        "recommended_mitigations": [_MITIGATIONS[k] for k, _ in top if k in _MITIGATIONS],
        "detailed_factors": score.factors,
    }


def generate_portfolio_report(assets: list[EnergyAsset], scores: list[RiskScore]) -> dict:
    score_map = {s.asset_id: s for s in scores}
    by_level: dict[str, list[str]] = {level.value: [] for level in RiskLevel}
    for asset in assets:
        s = score_map.get(asset.id)
        if s:
            by_level[s.risk_level.value].append(asset.name)

    sorted_scores = sorted(scores, key=lambda s: s.composite_score, reverse=True)
    avg = sum(s.composite_score for s in scores) / len(scores) if scores else 0.0

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "portfolio_summary": {
            "total_assets": len(assets),
            "average_risk_score": round(avg, 2),
            "assets_by_risk_level": {k: len(v) for k, v in by_level.items()},
            "asset_names_by_risk_level": by_level,
        },
        "highest_risk_assets": [
            {
                "asset_id": s.asset_id,
                "composite_score": s.composite_score,
                "risk_level": s.risk_level.value,
            }
            for s in sorted_scores[:5]
        ],
        "asset_reports": [
            generate_asset_report(a, score_map[a.id])
            for a in assets
            if a.id in score_map
        ],
    }


def to_json(report: dict, indent: int = 2) -> str:
    return json.dumps(report, indent=indent)
