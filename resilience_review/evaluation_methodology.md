# Methodology for Geospatial Evaluation of Energy Reliability
## Northeast Military Installation Resilience Review
**Duval County, Clay County & Jacksonville, FL**

---

## 1. Overview

This methodology provides a replicable, geospatially-grounded framework for evaluating energy reliability at and around military installations in Northeast Florida. It is designed to be executed using publicly available datasets and open-source GIS tools (QGIS, Python/GeoPandas, ArcGIS Pro), and to produce outputs usable in resilience planning, hazard mitigation updates, and installation master planning.

---

## 2. Core Analytical Framework

The evaluation follows a **Hazard × Exposure × Vulnerability × Adaptive Capacity** model, applied spatially at three scales:
- **Installation scale** — on-base generation, distribution, and critical load topology
- **Local utility scale** — substations, primary feeders, and transmission corridors within ~25 mi
- **Regional grid scale** — bulk transmission, generation mix, and interconnection topology for the Florida-Georgia region

---

## 3. Datasets and Sources

### 3.1 Energy Infrastructure

| Dataset | Source | Format | Notes |
|---|---|---|---|
| Electric Power Transmission Lines | EIA / HIFLD Open | Shapefile / GeoJSON | Voltage class, ownership |
| Electric Substations | EIA Form 860 / HIFLD | Shapefile | Name, voltage, county |
| Power Plants (generation) | EIA Form 860 | CSV + geocoded | Fuel type, capacity, age |
| Utility Service Territory Boundaries | EIA / state PUC | Shapefile | JEA, FPL, Clay Electric |
| Distributed Solar + Storage (SEIA) | SEIA / NREL | CSV | Aggregate by zip/county |
| Military Installation Boundaries | HIFLD / DoD | Shapefile | NAS Jax, NS Mayport, Camp Blanding |
| On-Installation Energy Assets | NAVFAC / AFCEC reports | PDF/tabular | Must be requested via FOIA or direct coordination |

### 3.2 Hazard and Climate Data

| Dataset | Source | Format | Notes |
|---|---|---|---|
| FEMA National Flood Hazard Layer (NFHL) | FEMA MSC | Shapefile | Zones AE, VE, X — critical for substation flood exposure |
| NOAA Sea Level Rise Scenarios (0.5–2.5m) | NOAA Digital Coast | Raster / viewer | Scenarios for 2050, 2075, 2100 |
| NOAA SLOSH Hurricane Surge Model | NHC / NOAA | Raster | Category 1–5 surge footprints |
| National Hurricane Center Best Track (HURDAT2) | NOAA NHC | CSV | Historical storm tracks 1851–present |
| USGS StreamStats / Flood Frequency | USGS | REST API | 100/500-yr flood peak discharge |
| Wildfire Hazard Potential | USFS RMRS | Raster | Camp Blanding WUI classification |
| Extreme Heat Index Projections | NOAA / NASA NEX-GDDP | NetCDF | Cooling load demand modeling |
| NOAA Precipitation Frequency (Atlas 14) | NOAA | Tabular/grid | Design storm inputs |

### 3.3 Socioeconomic and Operational Context

| Dataset | Source | Format | Notes |
|---|---|---|---|
| Critical Facilities (hospitals, EOCs) | HIFLD / county GIS | Shapefile | Shared grid load priorities |
| Census TIGER/LINE County Boundaries | US Census | Shapefile | Duval, Clay, Bradford |
| Road Network (for access/egress) | OpenStreetMap / FDOT | Shapefile | Restoration crew routing |
| DoD Installation Resilience Scorecards | OUSD(A&S) | PDF | Baseline metrics, if available |

---

## 4. Analytical Steps

### Step 1 — Infrastructure Inventory and Topology Mapping
Compile all transmission lines, substations, and service territories within a 30-mile buffer of each installation. Build a network topology model identifying: (a) injection points into each installation, (b) shared civilian-military infrastructure segments, and (c) single points of failure (SPOFs) defined as nodes whose removal disconnects any installation load.

### Step 2 — Hazard Overlay Analysis
Intersect each infrastructure element (substations, transmission segments, access roads) with:
- FEMA flood zones (AE, VE, X500)
- NOAA surge scenarios (Cat 1–4)
- SLR inundation layers (0.5m, 1.0m, 2.0m above current MHW)
- Wildfire Hazard Potential (Camp Blanding corridor)
- Extreme heat index grids (NOAA projections, 2040 and 2060)

Output: per-element hazard exposure score matrix.

### Step 3 — Vulnerability Scoring
Score each infrastructure element using:
- **Age proxy** (EIA Form 860 install year — older = higher vulnerability)
- **Redundancy** (number of alternate supply paths — single-feed = highest vulnerability)
- **Flood damage function** (USACE depth-damage curves for substation equipment)
- **Wind fragility** (HAZUS-MH fragility curves for transmission structures by voltage class)

### Step 4 — Criticality Weighting
Weight each element by the criticality of the military load it serves:
- Tier 1: Mission-critical operational loads (flight operations, command, weapon systems)
- Tier 2: Life safety and essential services (medical, water, communications)
- Tier 3: Support and administrative

Criticality data requires coordination with installation energy managers and may involve CUI-handling requirements.

### Step 5 — Risk Scoring and Prioritization
Combine hazard exposure × vulnerability × criticality into a composite risk score. Visualize as a choropleth or proportional symbol map. Identify top quartile elements for adaptation prioritization.

### Step 6 — Adaptive Capacity Assessment
Evaluate existing resilience measures: backup generator coverage (fuel type, rated duration), microgrid/islanding capability, mutual aid agreements, and planned utility hardening projects. Map gaps between current adaptive capacity and risk scores.

### Step 7 — Scenario Analysis
Run at least two scenarios: (a) current climate + current grid, and (b) 2050 climate projections (1.0m SLR + increased hurricane intensity) + planned grid upgrades. Compare risk scores to quantify the value of adaptation investments over time.

---

## 5. Tools and Workflow

```
Data Ingestion → QGIS / GeoPandas
Hazard Overlay → QGIS spatial join / Python shapely intersection
Vulnerability Scoring → Python pandas (tabular) + GeoPandas (spatial join)
Network Topology → NetworkX (Python) for SPOF identification
Visualization → Folium (interactive HTML) / QGIS map layouts
Reporting → Markdown / Word export
```

---

## 6. Knowledge and Data Gaps

### Critical Gaps (block analysis if unresolved)

| Gap | Description | Workaround |
|---|---|---|
| **On-installation asset data** | Exact locations of distribution panels, generator sets, and microgrid boundaries are not in public datasets | Request from NAVFAC Southeast / installation energy managers; use installation master plans |
| **Substation age and condition** | EIA Form 860 captures install year but not maintenance condition or remaining useful life | Utility coordination (JEA/FPL) or FOIA; use age as proxy |
| **Critical load topology** | Which circuits serve which operational loads at each installation | Requires CUI coordination with installation DPW/energy management offices |
| **Fuel supply chain data** | Backup generator fuel storage and resupply logistics not in public datasets | Defense Logistics Agency coordination |

### Significant Gaps (degrade analysis quality)

| Gap | Description | Workaround |
|---|---|---|
| **Distributed solar/storage inventory** | Rooftop solar on military facilities not fully captured in SEIA or EIA data | Satellite imagery classification (Maxar, Planet); NREL OpenPV partial coverage |
| **Real-time grid monitoring data** | No public feed of real-time grid status during events | JEA/FPL operations center coordination; post-event outage reports via EIA-417 |
| **SLOSH model resolution** | NOAA SLOSH 200m raster may be insufficient for precise substation-level flood risk in complex urban topography | ADCIRC high-resolution surge modeling (USACE/NOAA); LiDAR-based DEM |
| **Wildfire spread modeling** | No real-time or scenario-based fire spread data for Camp Blanding WUI corridor | FARSITE / FlamMap modeling using USFS fuel layers |
| **Underground cable locations** | JEA underground distribution routing not in HIFLD or other public sources | Utility coordination; assume overhead unless otherwise confirmed |

### Methodological Gaps

- **Cascading failure modeling**: The framework identifies SPOFs but does not model cascading interdependencies (e.g., telecom failure → SCADA failure → grid instability). A full interdependency analysis requires dedicated system-of-systems modeling.
- **Demand-side uncertainty**: Future energy demand at installations (EV fleet, HVAC load growth under higher temperatures, new mission sets) is not captured in current public datasets.
- **Equity and community resilience**: Off-installation community resilience (Jacksonville neighborhoods surrounding NAS Jacksonville) is not evaluated here but affects restoration timelines and mutual aid effectiveness.

---

## 7. Recommended Next Steps to Close Gaps

1. Request energy asset data package from NAVFAC Southeast under the Installation Energy Plan (IEP) framework
2. Initiate Cooperative Vulnerability Assessment (CVA) with JEA and FPL to obtain utility-specific infrastructure data under NDA
3. Commission LiDAR-based hydrodynamic model (ADCIRC) for NS Mayport substation surge risk — cost ~$80–120K, significant risk reduction value
4. Partner with Florida Sea Grant and University of Florida GeoPlan Center for regional SLR scenario mapping at sub-meter resolution
5. Integrate with DoD's REAP (Resilience and Energy Action Program) data platform as it matures

---

*Prepared for the Northeast Military Installation Resilience Review | May 2026*
