"""Address-point corroboration; not an independent ground-truth accuracy test."""

from __future__ import annotations
import re
from collections import defaultdict
from pyproj import Transformer
from shapely.geometry import shape, Point
from shapely.ops import transform
from .matching import normalize_street

TRANSFORMER = Transformer.from_crs(4326, 2263, always_xy=True)
MAX_DISTANCE_FT = 150.0
MIN_MARGIN_FT = 20.0
ENDPOINT_BUFFER_FT = 20.0


def exact_house(value):
    # Keep letters and fractions. Whitespace is not significant for 2527 B vs 2527B.
    return re.sub(r"\s+", "", str(value or "").upper())


def point_house(row):
    return exact_house(
        str(row.get("house_number", "")) + str(row.get("house_number_suffix", ""))
    )


def projected(geojson):
    return transform(TRANSFORMER.transform, shape(geojson))


def choose_spatial(
    distances,
    endpoint_distance,
    max_distance=MAX_DISTANCE_FT,
    min_margin=MIN_MARGIN_FT,
    endpoint_buffer=ENDPOINT_BUFFER_FT,
):
    """Return a conservative diagnostic suggestion; never a production assignment."""
    if not distances:
        return "", "no_same_street_geometry"
    ranked = sorted(distances.items(), key=lambda x: (x[1], x[0]))
    nearest, distance = ranked[0]
    if distance > max_distance:
        return "", "point_far_from_street"
    if len(ranked) > 1 and ranked[1][1] - distance < min_margin:
        return "", "close_competing_segments"
    if endpoint_distance < endpoint_buffer:
        return "", "near_segment_endpoint"
    return nearest, "spatially_distinct"


class AddressAudit:
    def __init__(self, points, segments):
        self.points = defaultdict(list)
        self.segments = defaultdict(list)
        self.by_id = defaultdict(list)
        for row in points:
            if row.get("address_status") in {"1", "2", "3", "5"} or not row.get(
                "the_geom"
            ):
                continue
            self.points[
                (normalize_street(row.get("full_street_name")), point_house(row))
            ].append(row)
        for row in segments:
            if not row.get("the_geom") or row.get("status") != "2":
                continue
            item = (str(row["physicalid"]), projected(row["the_geom"]), row)
            self.by_id[item[0]].append(item)
            # Full street/display names only; bare component names can omit direction/type.
            for name in {
                normalize_street(row.get("full_street_name")),
                normalize_street(row.get("stname_label")),
            } - {""}:
                self.segments[name].append(item)

    def inspect(self, row):
        street = normalize_street(row.get("violation_location_street_name"))
        house = exact_house(row.get("violation_location_house"))
        points = self.points[(street, house)] if house else []
        assigned = row.get("matched_physical_id", "")
        evidence = []
        for ap in points:
            point = projected(ap["the_geom"])
            distances = {}
            endpoints = {}
            for pid, geom, _ in self.segments[street]:
                distance = point.distance(geom)
                if pid not in distances or distance < distances[pid]:
                    distances[pid] = distance
                    lines = list(geom.geoms) if hasattr(geom, "geoms") else [geom]
                    line = min(lines, key=point.distance)
                    along = line.project(point)
                    endpoints[pid] = min(along, line.length - along)
            ranked = sorted(distances, key=lambda p: (distances[p], p))
            nearest = ranked[0] if ranked else ""
            suggestion, reason = choose_spatial(distances, endpoints.get(nearest, 0))
            assigned_distance = min(
                (point.distance(g) for _, g, _ in self.by_id.get(assigned, [])),
                default=None,
            )
            evidence.append(
                {
                    "addresspointid": ap["addresspointid"],
                    "bin": ap.get("bin", ""),
                    "validation": ap.get("validation", ""),
                    "address_source": ap.get("address_source", ""),
                    "address_status": ap.get("address_status", ""),
                    "zipcode": ap.get("zipcode", ""),
                    "longitude": ap["the_geom"]["coordinates"][0],
                    "latitude": ap["the_geom"]["coordinates"][1],
                    "nearest_physical_id": nearest,
                    "nearest_distance_ft": (
                        round(distances[nearest], 2) if nearest else None
                    ),
                    "runner_up_physical_id": ranked[1] if len(ranked) > 1 else "",
                    "runner_up_distance_ft": (
                        round(distances[ranked[1]], 2) if len(ranked) > 1 else None
                    ),
                    "endpoint_along_distance_ft": (
                        round(endpoints[nearest], 2) if nearest else None
                    ),
                    "assigned_distance_ft": (
                        round(assigned_distance, 2)
                        if assigned_distance is not None
                        else None
                    ),
                    "suggested_physical_id": suggestion,
                    "spatial_reason": reason,
                }
            )
        suggestions = {e["suggested_physical_id"] for e in evidence}
        if assigned and assigned not in self.by_id:
            status = "assigned_segment_missing_current_reference"
        elif not evidence:
            status = "no_exact_address_point"
        elif "" in suggestions:
            status = "spatial_review_required"
        elif len(suggestions) > 1:
            status = "address_points_disagree"
        elif assigned:
            status = (
                "corroborated"
                if suggestions == {assigned}
                else "assignment_discrepancy"
            )
        else:
            status = "possible_recovery"
        return {
            "ticket_number": row["ticket_number"],
            "house": row.get("violation_location_house", ""),
            "street": row.get("violation_location_street_name", ""),
            "zip": row.get("violation_location_zip_code", ""),
            "original_quality": row["match_quality"],
            "original_method": row["match_method"],
            "assigned_physical_id": assigned,
            "address_point_count": len(evidence),
            "audit_status": status,
            "suggested_physical_id": (
                next(iter(suggestions))
                if len(suggestions) == 1 and "" not in suggestions
                else ""
            ),
            "field_validated_point_present": any(
                e["validation"] == "2" for e in evidence
            ),
            "evidence": evidence,
        }
