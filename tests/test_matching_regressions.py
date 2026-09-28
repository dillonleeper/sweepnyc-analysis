from sweepnyc.matching import match_oath_to_cscl, normalize_street


def segment(**kwargs):
    return {"physicalid": "1", "full_stree": "WEST 46 STREET", "l_low_hn": "241", "l_high_hn": "259", "l_zip": "10036", **kwargs}


def address(house="245"):
    return {"violation_location_house": house, "violation_location_street_name": "W 46th St", "violation_location_zip_code": "10036"}


def test_no_assignment_outside_range():
    result = match_oath_to_cscl(address("999"), [segment()])
    assert result.physical_id is None
    assert result.quality == "unmatched"


def test_wrong_parity_not_confident():
    assert match_oath_to_cscl(address("246"), [segment()]).physical_id is None


def test_reversed_range():
    assert match_oath_to_cscl(address(), [segment(l_low_hn="259", l_high_hn="241")]).physical_id == "1"


def test_multiple_segments_remain_ambiguous():
    result = match_oath_to_cscl(address(), [segment(), segment(physicalid="2")])
    assert result.quality == "ambiguous"
    assert result.physical_id is None
    assert result.candidate_count == 2


def test_duplicate_rows_do_not_make_ambiguity():
    assert match_oath_to_cscl(address(), [segment(), segment()]).quality == "exact"


def test_direction_and_ordinal_variants():
    assert normalize_street("West 46th Street") == normalize_street("W 46 ST")

def test_avenue_prefix_and_direction_suffix():
    assert normalize_street("AVENUE OF THE AMERICAS") == normalize_street("AVE OF THE AMERICAS")
    assert normalize_street("7 AVENUE SOUTH") == normalize_street("7 AVE S")
    assert normalize_street("AVENUE A") == normalize_street("AVE A")


def test_letter_house_not_exact():
    assert match_oath_to_cscl(address("245B"), [segment()]).quality == "high_confidence"
