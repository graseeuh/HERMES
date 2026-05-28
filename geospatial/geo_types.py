from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class AssetType(Enum):
    POWER_LINE = "power_line"
    SUBSTATION = "substation"
    TRANSFORMER = "transformer"
    PIPELINE = "pipeline"
    REFINERY = "refinery"
    STORAGE_FACILITY = "storage_facility"
    SOLAR_FARM = "solar_farm"
    WIND_TURBINE = "wind_turbine"
    OFFSHORE_PLATFORM = "offshore_platform"


class HazardType(Enum):
    FLOOD = "flood"
    EARTHQUAKE = "earthquake"
    WILDFIRE = "wildfire"
    HURRICANE = "hurricane"


class RiskLevel(Enum):
    MINIMAL = "minimal"    # 0–19
    LOW = "low"            # 20–39
    MEDIUM = "medium"      # 40–59
    HIGH = "high"          # 60–79
    CRITICAL = "critical"  # 80–100


@dataclass
class Coordinate:
    lat: float
    lon: float

    def __post_init__(self) -> None:
        if not (-90 <= self.lat <= 90):
            raise ValueError(f"Latitude {self.lat} out of range [-90, 90]")
        if not (-180 <= self.lon <= 180):
            raise ValueError(f"Longitude {self.lon} out of range [-180, 180]")


@dataclass
class EnergyAsset:
    id: str
    name: str
    asset_type: AssetType
    location: Coordinate
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class HazardZone:
    zone_id: str
    hazard_type: HazardType
    center: Coordinate
    radius_km: float
    severity: float  # 0.0–1.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not (0.0 <= self.severity <= 1.0):
            raise ValueError(f"Severity {self.severity} out of range [0.0, 1.0]")
        if self.radius_km <= 0:
            raise ValueError(f"radius_km must be positive, got {self.radius_km}")


@dataclass
class ProximityFeature:
    feature_id: str
    feature_type: str  # "population_center", "hospital", "school", "military", "water_treatment"
    location: Coordinate
    radius_km: float
    weight: float = 1.0  # relative importance within its type


@dataclass
class RiskScore:
    asset_id: str
    hazard_score: float
    climate_score: float
    proximity_score: float
    security_score: float
    composite_score: float
    risk_level: RiskLevel
    factors: dict[str, Any]
