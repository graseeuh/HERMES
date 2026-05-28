"""Tests for tools/geospatial — geospatial energy risk analysis tools."""
import json
import math
import pytest

from geospatial.geo_types import (
    AssetType,
    Coordinate,
    EnergyAsset,
    HazardType,
    HazardZone,
    ProximityFeature,
    RiskLevel,
    RiskScore,
)
from geospatial.hazard_analyzer import analyze_hazard, haversine_km
from geospatial.climate_analyzer import analyze_climate
from geospatial.proximity_analyzer import analyze_proximity
from geospatial.security_analyzer import analyze_security
from geospatial.risk_aggregator import score_asset, score_portfolio, DEFAULT_WEIGHTS, _risk_level
from geospatial.geojson_exporter import export_portfolio, to_json as geojson_to_json
from geospatial.report_generator import (
    generate_asset_report,
    generate_portfolio_report,
    to_json as report_to_json,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def london() -> Coordinate:
    return Coordinate(lat=51.5, lon=-0.1)


@pytest.fixture()
def dubai() -> Coordinate:
    return Coordinate(lat=25.2, lon=55.3)


@pytest.fixture()
def substation(london) -> EnergyAsset:
    return EnergyAsset(
        id="sub-001",
        name="London Grid Substation",
        asset_type=AssetType.SUBSTATION,
        location=london,
        metadata={"voltage_kv": 400, "critical": True},
    )


@pytest.fixture()
def solar_farm(dubai) -> EnergyAsset:
    return EnergyAsset(
        id="sol-001",
        name="Dubai Solar Farm",
        asset_type=AssetType.SOLAR_FARM,
        location=dubai,
    )


@pytest.fixture()
def offshore_platform() -> EnergyAsset:
    return EnergyAsset(
        id="off-001",
        name="North Sea Platform",
        asset_type=AssetType.OFFSHORE_PLATFORM,
        location=Coordinate(lat=57.0, lon=2.0),
    )


@pytest.fixture()
def flood_zone_near_london(london) -> HazardZone:
    return HazardZone(
        zone_id="fz-001",
        hazard_type=HazardType.FLOOD,
        center=Coordinate(lat=london.lat + 0.05, lon=london.lon),
        radius_km=20.0,
        severity=0.8,
    )


@pytest.fixture()
def earthquake_zone_far() -> HazardZone:
    return HazardZone(
        zone_id="eq-001",
        hazard_type=HazardType.EARTHQUAKE,
        center=Coordinate(lat=10.0, lon=10.0),
        radius_km=50.0,
        severity=0.9,
    )


@pytest.fixture()
def hospital_near_london(london) -> ProximityFeature:
    return ProximityFeature(
        feature_id="hosp-001",
        feature_type="hospital",
        location=Coordinate(lat=london.lat + 0.01, lon=london.lon),
        radius_km=5.0,
    )


@pytest.fixture()
def population_center(london) -> ProximityFeature:
    return ProximityFeature(
        feature_id="pop-001",
        feature_type="population_center",
        location=Coordinate(lat=london.lat, lon=london.lon + 0.02),
        radius_km=10.0,
        weight=0.8,
    )


# ---------------------------------------------------------------------------
# Coordinate validation
# ---------------------------------------------------------------------------

class TestCoordinate:
    def test_valid_coordinate(self):
        c = Coordinate(lat=45.0, lon=90.0)
        assert c.lat == 45.0
        assert c.lon == 90.0

    def test_boundary_values(self):
        Coordinate(lat=-90, lon=-180)
        Coordinate(lat=90, lon=180)

    def test_invalid_latitude(self):
        with pytest.raises(ValueError, match="Latitude"):
            Coordinate(lat=91.0, lon=0.0)

    def test_invalid_longitude(self):
        with pytest.raises(ValueError, match="Longitude"):
            Coordinate(lat=0.0, lon=181.0)


# ---------------------------------------------------------------------------
# Haversine distance
# ---------------------------------------------------------------------------

class TestHaversine:
    def test_same_point_is_zero(self, london):
        assert haversine_km(london, london) == pytest.approx(0.0, abs=1e-6)

    def test_known_distance(self):
        # London to Paris ≈ 340 km
        london = Coordinate(lat=51.5, lon=-0.1)
        paris = Coordinate(lat=48.85, lon=2.35)
        dist = haversine_km(london, paris)
        assert 330 < dist < 350

    def test_antipodal_points(self):
        a = Coordinate(lat=0, lon=0)
        b = Coordinate(lat=0, lon=180)
        dist = haversine_km(a, b)
        assert dist == pytest.approx(math.pi * 6371.0, rel=0.01)

    def test_symmetry(self, london, dubai):
        assert haversine_km(london, dubai) == pytest.approx(haversine_km(dubai, london), rel=1e-9)


# ---------------------------------------------------------------------------
# HazardZone validation
# ---------------------------------------------------------------------------

class TestHazardZone:
    def test_invalid_severity_too_high(self, london):
        with pytest.raises(ValueError, match="Severity"):
            HazardZone("z1", HazardType.FLOOD, london, 10.0, severity=1.5)

    def test_invalid_radius(self, london):
        with pytest.raises(ValueError, match="radius_km"):
            HazardZone("z1", HazardType.FLOOD, london, radius_km=-1.0, severity=0.5)


# ---------------------------------------------------------------------------
# Hazard analyzer
# ---------------------------------------------------------------------------

class TestHazardAnalyzer:
    def test_no_zones_scores_zero(self, substation):
        score, factors = analyze_hazard(substation, [])
        assert score == 0.0
        assert all(v == 0.0 for v in factors.values())

    def test_asset_inside_flood_zone(self, substation, flood_zone_near_london):
        score, factors = analyze_hazard(substation, [flood_zone_near_london])
        assert score > 0
        assert factors["flood_exposure"] > 0
        assert factors["earthquake_exposure"] == 0.0

    def test_asset_outside_zone_scores_zero(self, solar_farm, flood_zone_near_london):
        # solar_farm is in Dubai, flood zone is near London
        score, _ = analyze_hazard(solar_farm, [flood_zone_near_london])
        assert score == 0.0

    def test_score_bounded(self, substation, flood_zone_near_london):
        score, _ = analyze_hazard(substation, [flood_zone_near_london])
        assert 0.0 <= score <= 100.0

    def test_center_of_zone_scores_highest(self, london):
        center_asset = EnergyAsset("c", "Center", AssetType.SUBSTATION, london)
        offset_asset = EnergyAsset("o", "Offset", AssetType.SUBSTATION, Coordinate(london.lat + 0.1, london.lon))
        zone = HazardZone("z", HazardType.FLOOD, london, 50.0, severity=1.0)
        center_score, _ = analyze_hazard(center_asset, [zone])
        offset_score, _ = analyze_hazard(offset_asset, [zone])
        assert center_score > offset_score

    def test_all_hazard_types_recorded(self, substation, london):
        zones = [
            HazardZone("f", HazardType.FLOOD, london, 10.0, 0.5),
            HazardZone("e", HazardType.EARTHQUAKE, london, 10.0, 0.5),
            HazardZone("w", HazardType.WILDFIRE, london, 10.0, 0.5),
            HazardZone("h", HazardType.HURRICANE, london, 10.0, 0.5),
        ]
        _, factors = analyze_hazard(substation, zones)
        assert set(factors.keys()) == {
            "flood_exposure", "earthquake_exposure", "wildfire_exposure", "hurricane_exposure"
        }


# ---------------------------------------------------------------------------
# Climate analyzer
# ---------------------------------------------------------------------------

class TestClimateAnalyzer:
    def test_score_bounded(self, solar_farm):
        score, _ = analyze_climate(solar_farm)
        assert 0.0 <= score <= 100.0

    def test_tropical_asset_higher_heat_stress_than_polar(self):
        tropical = EnergyAsset("t", "Tropical", AssetType.SOLAR_FARM, Coordinate(lat=10.0, lon=0.0))
        polar = EnergyAsset("p", "Polar", AssetType.SOLAR_FARM, Coordinate(lat=80.0, lon=0.0))
        t_score, t_factors = analyze_climate(tropical)
        p_score, p_factors = analyze_climate(polar)
        assert t_factors["heat_stress"] > p_factors["heat_stress"]

    def test_offshore_platform_high_sea_level(self, offshore_platform):
        score, factors = analyze_climate(offshore_platform)
        assert factors["sea_level_exposure"] >= 0.90

    def test_coastal_asset_higher_sea_level_than_inland(self):
        coast_pt = Coordinate(lat=51.5, lon=1.5)
        inland_pt = Coordinate(lat=51.5, lon=-2.0)
        coastline = [Coordinate(lat=51.5, lon=1.5)]
        coast_asset = EnergyAsset("c", "Coast", AssetType.SUBSTATION, coast_pt)
        inland_asset = EnergyAsset("i", "Inland", AssetType.SUBSTATION, inland_pt)
        _, c_factors = analyze_climate(coast_asset, coastline)
        _, i_factors = analyze_climate(inland_asset, coastline)
        assert c_factors["sea_level_exposure"] > i_factors["sea_level_exposure"]

    def test_heat_sensitive_asset_higher_than_non_sensitive(self):
        loc = Coordinate(lat=20.0, lon=0.0)
        transformer = EnergyAsset("t", "Tx", AssetType.TRANSFORMER, loc)
        solar = EnergyAsset("s", "Solar", AssetType.SOLAR_FARM, loc)
        _, tx_factors = analyze_climate(transformer)
        _, sol_factors = analyze_climate(solar)
        assert tx_factors["heat_stress"] > sol_factors["heat_stress"]


# ---------------------------------------------------------------------------
# Proximity analyzer
# ---------------------------------------------------------------------------

class TestProximityAnalyzer:
    def test_no_features_scores_zero(self, substation):
        score, factors = analyze_proximity(substation, [])
        assert score == 0.0
        assert factors == {}

    def test_asset_inside_hospital_radius(self, substation, hospital_near_london):
        score, factors = analyze_proximity(substation, [hospital_near_london])
        assert score > 0
        assert "hospital" in factors

    def test_asset_outside_feature_radius(self, solar_farm, hospital_near_london):
        # solar_farm in Dubai, hospital near London
        score, _ = analyze_proximity(solar_farm, [hospital_near_london])
        assert score == 0.0

    def test_multiple_categories_accumulate(self, substation, hospital_near_london, population_center):
        score_single, _ = analyze_proximity(substation, [hospital_near_london])
        score_both, _ = analyze_proximity(substation, [hospital_near_london, population_center])
        assert score_both > score_single

    def test_score_bounded(self, substation, hospital_near_london, population_center):
        score, _ = analyze_proximity(substation, [hospital_near_london, population_center])
        assert 0.0 <= score <= 100.0


# ---------------------------------------------------------------------------
# Security analyzer
# ---------------------------------------------------------------------------

class TestSecurityAnalyzer:
    def test_score_bounded(self, substation):
        score, _ = analyze_security(substation)
        assert 0.0 <= score <= 100.0

    def test_critical_asset_scores_higher_than_non_critical(self, london):
        critical = EnergyAsset("c", "Crit", AssetType.SUBSTATION, london, metadata={"critical": True})
        normal = EnergyAsset("n", "Norm", AssetType.SUBSTATION, london)
        c_score, _ = analyze_security(critical)
        n_score, _ = analyze_security(normal)
        assert c_score > n_score

    def test_more_access_routes_increases_score(self, substation):
        score_1, _ = analyze_security(substation, access_route_count=1)
        score_4, _ = analyze_security(substation, access_route_count=4)
        assert score_4 > score_1

    def test_nearby_settlement_lowers_isolation(self, london):
        asset = EnergyAsset("a", "A", AssetType.SUBSTATION, london)
        nearby = ProximityFeature("s", "population_center", Coordinate(london.lat + 0.01, london.lon), 5.0)
        _, factors_with = analyze_security(asset, settlements=[nearby])
        _, factors_without = analyze_security(asset, settlements=[])
        assert factors_with["isolation_index"] < factors_without["isolation_index"]

    def test_high_risk_asset_type(self, london):
        refinery = EnergyAsset("r", "Ref", AssetType.REFINERY, london)
        wind = EnergyAsset("w", "Wind", AssetType.WIND_TURBINE, london)
        r_score, _ = analyze_security(refinery)
        w_score, _ = analyze_security(wind)
        assert r_score > w_score


# ---------------------------------------------------------------------------
# Risk aggregator
# ---------------------------------------------------------------------------

class TestRiskAggregator:
    def test_risk_level_thresholds(self):
        assert _risk_level(85) == RiskLevel.CRITICAL
        assert _risk_level(65) == RiskLevel.HIGH
        assert _risk_level(50) == RiskLevel.MEDIUM
        assert _risk_level(30) == RiskLevel.LOW
        assert _risk_level(10) == RiskLevel.MINIMAL

    def test_score_asset_returns_risk_score(self, substation):
        result = score_asset(substation)
        assert isinstance(result, RiskScore)
        assert result.asset_id == substation.id
        assert 0.0 <= result.composite_score <= 100.0

    def test_score_asset_composite_reflects_weights(self, substation):
        result = score_asset(substation)
        expected = (
            result.hazard_score * DEFAULT_WEIGHTS["hazard"]
            + result.climate_score * DEFAULT_WEIGHTS["climate"]
            + result.proximity_score * DEFAULT_WEIGHTS["proximity"]
            + result.security_score * DEFAULT_WEIGHTS["security"]
        )
        assert result.composite_score == pytest.approx(expected, abs=0.01)

    def test_custom_weights_applied(self, substation, flood_zone_near_london):
        result_default = score_asset(substation, hazard_zones=[flood_zone_near_london])
        result_hazard_heavy = score_asset(
            substation,
            hazard_zones=[flood_zone_near_london],
            weights={"hazard": 0.90, "climate": 0.05, "proximity": 0.03, "security": 0.02},
        )
        # Heavier hazard weight should push score closer to hazard_score
        assert abs(result_hazard_heavy.composite_score - result_hazard_heavy.hazard_score) < abs(
            result_default.composite_score - result_default.hazard_score
        )

    def test_score_portfolio_returns_one_per_asset(self, substation, solar_farm):
        results = score_portfolio([substation, solar_farm])
        assert len(results) == 2
        ids = {r.asset_id for r in results}
        assert ids == {substation.id, solar_farm.id}

    def test_factors_dict_has_four_categories(self, substation):
        result = score_asset(substation)
        assert set(result.factors.keys()) == {"hazard", "climate", "proximity", "security"}


# ---------------------------------------------------------------------------
# GeoJSON exporter
# ---------------------------------------------------------------------------

class TestGeoJSONExporter:
    def test_export_produces_feature_collection(self, substation, solar_farm):
        fc = export_portfolio([substation, solar_farm])
        assert fc["type"] == "FeatureCollection"
        assert len(fc["features"]) == 2

    def test_feature_geometry_lon_lat_order(self, substation):
        fc = export_portfolio([substation])
        coords = fc["features"][0]["geometry"]["coordinates"]
        assert coords == [substation.location.lon, substation.location.lat]

    def test_risk_properties_present_when_scores_supplied(self, substation):
        score = score_asset(substation)
        fc = export_portfolio([substation], scores=[score])
        props = fc["features"][0]["properties"]
        assert "risk_composite" in props
        assert "risk_level" in props
        assert "marker_color" in props

    def test_no_risk_properties_without_scores(self, substation):
        fc = export_portfolio([substation])
        props = fc["features"][0]["properties"]
        assert "risk_composite" not in props

    def test_to_json_is_valid_json(self, substation, solar_farm):
        fc = export_portfolio([substation, solar_farm])
        raw = geojson_to_json(fc)
        parsed = json.loads(raw)
        assert parsed["type"] == "FeatureCollection"

    def test_asset_metadata_in_properties(self, substation):
        fc = export_portfolio([substation])
        props = fc["features"][0]["properties"]
        assert props["voltage_kv"] == 400


# ---------------------------------------------------------------------------
# Report generator
# ---------------------------------------------------------------------------

class TestReportGenerator:
    def test_asset_report_structure(self, substation):
        score = score_asset(substation)
        report = generate_asset_report(substation, score)
        assert report["asset_id"] == substation.id
        assert "risk_summary" in report
        assert "top_risk_factors" in report
        assert "recommended_mitigations" in report

    def test_top_risk_factors_sorted_descending(self, substation, flood_zone_near_london):
        score = score_asset(substation, hazard_zones=[flood_zone_near_london])
        report = generate_asset_report(substation, score)
        values = [f["value"] for f in report["top_risk_factors"]]
        assert values == sorted(values, reverse=True)

    def test_portfolio_report_structure(self, substation, solar_farm):
        assets = [substation, solar_farm]
        scores = score_portfolio(assets)
        report = generate_portfolio_report(assets, scores)
        assert report["portfolio_summary"]["total_assets"] == 2
        assert "highest_risk_assets" in report
        assert "asset_reports" in report
        assert "generated_at" in report

    def test_portfolio_average_score_correct(self, substation, solar_farm):
        assets = [substation, solar_farm]
        scores = score_portfolio(assets)
        report = generate_portfolio_report(assets, scores)
        expected_avg = sum(s.composite_score for s in scores) / len(scores)
        assert report["portfolio_summary"]["average_risk_score"] == pytest.approx(expected_avg, abs=0.01)

    def test_highest_risk_assets_at_most_five(self):
        assets = [
            EnergyAsset(f"a{i}", f"Asset {i}", AssetType.SUBSTATION, Coordinate(lat=float(i), lon=0.0))
            for i in range(10)
        ]
        scores = score_portfolio(assets)
        report = generate_portfolio_report(assets, scores)
        assert len(report["highest_risk_assets"]) <= 5

    def test_to_json_is_valid_json(self, substation):
        score = score_asset(substation)
        report = generate_asset_report(substation, score)
        raw = report_to_json(report)
        parsed = json.loads(raw)
        assert parsed["asset_id"] == substation.id

    def test_risk_level_distribution_sums_to_total(self, substation, solar_farm, offshore_platform):
        assets = [substation, solar_farm, offshore_platform]
        scores = score_portfolio(assets)
        report = generate_portfolio_report(assets, scores)
        level_counts = report["portfolio_summary"]["assets_by_risk_level"]
        assert sum(level_counts.values()) == len(assets)
