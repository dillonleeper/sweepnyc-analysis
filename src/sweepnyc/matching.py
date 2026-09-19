"""Street-segment matching helpers for the Phase 1 pilot."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Iterable


DIRECTIONALS = {"NORTH": "N", "SOUTH": "S", "EAST": "E", "WEST": "W"}\n\nSTREET_SUFFIXES = {
    "STREET": "ST",
    "ST": "ST",
    "AVENUE": "AVE",
    "AVE": "AVE",
    "AV": "AVE",
    "ROAD": "RD",
    "RD": "RD",
    "BOULEVARD": "BLVD",
    "BLVD": "BLVD",
    "PLACE": "PL",
    "PL": "PL",
    "DRIVE": "DR",
    "DR": "DR",
    "LANE": "LN",
    "LN": "LN",
    "PARKWAY": "PKWY",
    "PKWY": "PKWY",
    "COURT": "CT",
    "CT": "CT",
    "TERRACE": "TER",
    "TER": "TER",
    "HIGHWAY": "HWY",
    "HWY": "HWY",
}


@dataclass(frozen=True)
class MatchResult:
    physical_id: str | None
    quality: str
    method: str
    candidate_count: int


def normalize_street(value: str | None) -> str:
    if not value:
        return ""
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    value = value.upper().replace("&", " AND ")
    value = re.sub(r"[^A-Z0-9 ]+", " ", value)
    tokens = [t for t in re.split(r"\s+", value.strip()) if t]
    if tokens and tokens[-1] in STREET_SUFFIXES:
        tokens[-1] = STREET_SUFFIXES[tokens[-1]]
    return " ".join(tokens)


def house_number_key(value: str | None) -> tuple[int, ...] | None:
    """Convert NYC house numbers to a comparable numeric tuple.

    Examples:
      245 -> (245,)
      45-12 -> (45, 12)

    Letter suffixes are ignored in Phase 1 and should be audited separately.
    """
    if not value:
        return None
    value = value.strip().upper()
    nums = re.findall(r"\d+", value)
    if not nums:
        return None
    return tuple(int(n) for n in nums[:2])


def _same_shape_between(house: tuple[int, ...], low: tuple[int, ...] | None, high: tuple[int, ...] | None) -> bool:
    if low is None or high is None:
        return False
    if len(house) != len(low) or len(house) != len(high):
        return False
    return low <= house <= high


def _parity_match(house: tuple[int, ...], low: tuple[int, ...] | None, high: tuple[int, ...] | None) -> bool:
    if low is None or high is None or len(house) != len(low) or len(house) != len(high):
        return False
    # NYC address parity is determined by the final numeric component.
    return (house[-1] % 2) == (low[-1] % 2) == (high[-1] % 2)


def candidate_street_names(row: dict) -> set[str]:
    names = {
        normalize_street(row.get("full_stree")),
        normalize_street(row.get("st_name")),
        normalize_street(row.get("st_label")),
    }
    return {n for n in names if n}


def match_oath_to_cscl(oath: dict, cscl_rows: Iterable[dict]) -> MatchResult:
    street = normalize_street(oath.get("violation_location_street_name"))
    house = house_number_key(oath.get("violation_location_house"))
    zipcode = str(oath.get("violation_location_zip_code") or "").strip()

    if not street or house is None:
        return MatchResult(None, "unmatched", "missing_address", 0)

    name_matches = [r for r in cscl_rows if street in candidate_street_names(r)]
    if zipcode:
        zip_matches = [
            r for r in name_matches
            if zipcode in {str(r.get("l_zip") or "").strip(), str(r.get("r_zip") or "").strip()}
        ]
        if zip_matches:
            name_matches = zip_matches

    ranged = []
    for row in name_matches:
        left_low = house_number_key(row.get("l_low_hn"))
        left_high = house_number_key(row.get("l_high_hn"))
        right_low = house_number_key(row.get("r_low_hn"))
        right_high = house_number_key(row.get("r_high_hn"))

        left_ok = _same_shape_between(house, left_low, left_high) and _parity_match(house, left_low, left_high)
        right_ok = _same_shape_between(house, right_low, right_high) and _parity_match(house, right_low, right_high)
        if left_ok or right_ok:
            ranged.append(row)

    physical_ids = sorted({str(r.get("physicalid")) for r in ranged if r.get("physicalid") is not None})
    if len(physical_ids) == 1:
        return MatchResult(physical_ids[0], "exact", "street_house_range", 1)
    if len(physical_ids) > 1:
        return MatchResult(None, "ambiguous", "multiple_house_range_segments", len(physical_ids))

    # A unique street+ZIP candidate is useful diagnostically, but is not strong enough
    # to force a segment assignment without a house-range match.
    name_ids = sorted({str(r.get("physicalid")) for r in name_matches if r.get("physicalid") is not None})
    if len(name_ids) == 1:
        return MatchResult(name_ids[0], "high_confidence", "unique_street_zip_fallback", 1)
    if len(name_ids) > 1:
        return MatchResult(None, "ambiguous", "street_match_no_house_range", len(name_ids))
    return MatchResult(None, "unmatched", "no_street_match", 0)
