from sweepnyc.matching import house_number_key, match_oath_to_cscl, normalize_street


def test_normalize_street():
    assert normalize_street("East 42nd Street") == "E 42 ST"
    assert normalize_street("3rd Avenue") == "3 AVE"


def test_house_number_key():
    assert house_number_key("245") == (245,)
    assert house_number_key("45-12") == (45, 12)


def test_unique_range_match():
    oath = {
        "violation_location_house": "245",
        "violation_location_street_name": "West 46th Street",
        "violation_location_zip_code": "10036",
    }
    cscl = [
        {
            "physicalid": "123",
            "full_stree": "WEST 46 STREET",
            "st_name": "WEST 46 STREET",
            "st_label": "W 46 ST",
            "l_low_hn": "241",
            "l_high_hn": "259",
            "r_low_hn": "240",
            "r_high_hn": "260",
            "l_zip": "10036",
            "r_zip": "10036",
        }
    ]
    result = match_oath_to_cscl(oath, cscl)
    assert result.physical_id == "123"
    assert result.quality == "exact"


def test_missing_address_is_unmatched():
    result = match_oath_to_cscl({}, [])
    assert result.quality == "unmatched"
    assert result.method == "missing_address"
