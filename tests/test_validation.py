import pytest
from sweepnyc.validation import exact_house, point_house, choose_spatial, AddressAudit


def test_suffix_and_fraction_preserved():
    assert exact_house("2527 B") == "2527B"
    assert exact_house("615 1/2") != "615"
    assert point_house({"house_number": "245", "house_number_suffix": "B"}) == "245B"


@pytest.mark.parametrize(
    "distances,endpoint,expected",
    [
        ({"a": 30, "b": 80}, 70, ("a", "spatially_distinct")),
        ({"a": 30, "b": 35}, 70, ("", "close_competing_segments")),
        ({"a": 151}, 70, ("", "point_far_from_street")),
        ({"a": 30, "b": 80}, 19, ("", "near_segment_endpoint")),
        ({}, 70, ("", "no_same_street_geometry")),
        ({"a": 150, "b": 170}, 20, ("a", "spatially_distinct")),
    ],
)
def test_spatial_review_thresholds(distances, endpoint, expected):
    assert choose_spatial(distances, endpoint) == expected


def segment(pid="1"):
    return {
        "physicalid": pid,
        "status": "2",
        "full_street_name": "W 46 ST",
        "the_geom": {
            "type": "LineString",
            "coordinates": [[-73.99, 40.75], [-73.99, 40.752]],
        },
    }


def point(**kwargs):
    return {
        "addresspointid": "p1",
        "house_number": "245",
        "full_street_name": "W 46 ST",
        "validation": "2",
        "the_geom": {"type": "Point", "coordinates": [-73.9901, 40.751]},
        **kwargs,
    }


def oath(**kwargs):
    return {
        "ticket_number": "t1",
        "violation_location_house": "245",
        "violation_location_street_name": "West 46th Street",
        "matched_physical_id": "1",
        "match_quality": "exact",
        "match_method": "street_house_range",
        **kwargs,
    }


def test_missing_historical_id_is_not_address_error():
    result = AddressAudit([point()], [segment("2")]).inspect(oath())
    assert result["audit_status"] == "assigned_segment_missing_current_reference"


def test_retired_point_is_excluded():
    result = AddressAudit([point(address_status="5")], [segment()]).inspect(oath())
    assert result["audit_status"] == "no_exact_address_point"


def test_exact_point_corroborates_but_does_not_assign_unresolved():
    audit = AddressAudit([point()], [segment()])
    assert audit.inspect(oath())["audit_status"] == "corroborated"
    result = audit.inspect(oath(matched_physical_id="", match_quality="ambiguous"))
    assert result["audit_status"] == "possible_recovery"
    assert result["assigned_physical_id"] == ""


def test_letter_suffix_not_dropped_for_point_lookup():
    audit = AddressAudit([point()], [segment()])
    assert (
        audit.inspect(oath(violation_location_house="245B"))["audit_status"]
        == "no_exact_address_point"
    )


def test_multiple_points_disagree_stays_unresolved():
    distant = segment("2")
    distant["the_geom"]["coordinates"] = [[-73.99, 40.753], [-73.99, 40.755]]
    second = point(
        addresspointid="p2",
        the_geom={"type": "Point", "coordinates": [-73.9901, 40.754]},
    )
    result = AddressAudit([point(), second], [segment(), distant]).inspect(oath())
    assert result["audit_status"] == "address_points_disagree"
    assert result["suggested_physical_id"] == ""
